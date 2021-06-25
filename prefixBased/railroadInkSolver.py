
from gurobipy import Model, GRB, quicksum
from gurobipy import *
from board import Board, Tile, Side, EdgeType, Piece, NUM_ROWS, NUM_COLS, BASIC_PIECES, JUNCTION_PIECES, SPECIAL_PIECES, START_PIECES, SWITCH_PIECES, NUM_STARTS
from board import *
import csv
import numpy as np
import os
import shutil
import sys
import contextlib
import time

RESULTS_FOLDER = "results"
RESULTS_CSV = "points.csv"
MOVES_CSV = "moves.csv"


"""
returns a list of all the prefixes of the supplied tuple
"""
def prefixes(tup):
    return [tup[:i] for i in range(len(tup)+1)]

"""
class containing the tools required to provide a next move in a railroad ink game
this is supplied with a current board, a list of possible turns and an objective to use
"""
class RailroadInkSolver:
    
    """
    Constructor.
    To understand a game we need:
    board - object that contains the current placements of all previously played tiles
    turn - the turn we are up to
    dice_rolls - a list of all the remaining dice rolls, with each remaining turn being a list of the possible 
            dice rolls on that turn
    objective - which objective function to use, the possible objective functions are:
            "expected-score"
    specials - whether or not to consider special moves in the construction
    isolated_pieces - how to handle isolated pieces, options are "lazy" for using lazy constraints or "relief"
            for using a flow problem
    connecting_exits - whether to score points for connecting exits
    longest_paths - whether to score points for the longest paths
    errors - whether to score/lose points for errors
    open_ends - whether to attribute any points for open ends
    open_end_points - an array of the value given to open ends on each turn
    fake_connections - whether fake connections can be added (which cost points)
    fake_connections_cost - the cost associated with any fake placements
    fake_connections_max - the maximum number of fake connections that can be made on any turn
    internal_sinks - if True, then adds framework for connecting exits internally to ensure they are not closed off
    internal_sink_scores - determines how many points are scored for internal super sink connections each turn
    """
    def __init__(self, board, turn, dice_rolls, objective, specials=True, 
                 isolated_pieces="lazy",
                 connecting_exits=True, longest_paths=True, errors=True,
                 open_ends=False, open_end_points=[2.5, 2.5, 2, 1.6, 1.4, 0.5, 0],
                 fake_connections=False, fake_connections_cost=[0.6,0.6,0.8,1,1.5,2.5,4], fake_connections_max=[6,10,18,16,12,6,0],
                 internal_sinks=False, internal_sink_scores=[3,3,2.5,2,1.5,1,0]):
        self._board = board
        self._turn = turn
        self._dice_rolls = dice_rolls
        self._objective = objective
        self._specials = specials
        self._isolated_pieces = isolated_pieces
        self._connecting_exits = connecting_exits
        self._longest_paths = longest_paths
        self._errors = errors
        self._open_ends = open_ends
        self._open_end_points = open_end_points
        self._fake_connections = fake_connections
        self._fake_connections_cost = fake_connections_cost
        self._fake_connections_max = fake_connections_max
        self._internal_sinks = internal_sinks
        self._internal_sink_scores = internal_sink_scores
        #check for if there is even a special to be played, don't add them to the model if there isn't
        if self._board.all_specials_used():
            self._specials = False
        #calculate the turn index for the final move for indexing into scoring arrays
        self._end_turn_index = self._turn - 2 + len(dice_rolls)
    
    """
    generates all possible scenarios using the dice rolls. Does this recursively so must be passed lists to build
    currentList - the current scenario 
    D - list of all final scenarios
    C - list of every step in every scenario
    to generate all possible scenarios, call with self._generate_scenarios([], D, C) with D, C initialise as []
    """
    def _generate_scenarios(self, currentList, D, C):
        if len(currentList) == len(self._dice_rolls):
            D += [tuple(currentList)]
        else:
            nextIndex = len(currentList)
            for nextVal in range(len(self._dice_rolls[nextIndex])):
                currentList += [nextVal]
                self._generate_scenarios(currentList, D, C)
        C += [tuple(currentList)]
        if len(currentList) > 0:
            currentList.pop()    
    
    """
    create and solve an IP that gives the solutions to the railroad ink problem
    folder - a folder to print all information to, this will include the log, the results csv and any pictures,
            saves to "last-run" if no folder is specified, if None will not do any saving at all
    linear - if True, runs an LP, if False runs the IP
    printOutput - whether to print Gurobi output to stdout
    printD - a list of scenarios to print, or "all" if all scenarios should be printed, default is to not print
    seed - the seed to use for gurobi
    tune - if non-zero, will perform a tune with the given length of time instead of a normal search
    lazy_constraints - whether or not to include lazy constraints
    """
    def solve(self, folder="last-run", linear=False, printOutput=False, printD=[], seed=0, tune=0,
              lazy_constraints=True):

        self._start_time = time.time()
        
        if folder != None:
            folder = RESULTS_FOLDER + "/" + folder #update the folder name, always in the RESULTS top folder
            
            #create an empty folder to store all the results in
            self._create_empty_folder(folder)
        
        #create the model
        self.m = Model("Railroad Ink")
        
        self._create_sets()
        
        self._create_variables(linear)
        
        self._legal_constraints()
        if self._connecting_exits:
            self._joining_exits_constraints() 
        if self._longest_paths:
            self._longest_path_constraints()
        self._scoring_constraints()
        
        
        self._set_objective()
        
        #for some reason defining the callback in this function is the only way I seem to be able
        #to get the callback to play with Python's classes
        def Callback(model, where):
            self._callback(model, where)

        #redirect all output in this context, potentially to nowhere if we are not printing to stdout
        with contextlib.redirect_stdout(self._print_stream_location(printOutput)):
            self._set_gurobi_parameters(seed, folder, tune, lazy_constraints)
            
            if tune == 0:
                #OPTIMIZE
                if lazy_constraints:
                    self.m.optimize(Callback)
                else:
                    self.m.optimize()
            else:
                self.m.tune()
        
            #all logging is over, point the logfile somewhere else
            #this removes Gurobi's reference to the needed file so that it can be deleted
            self.m.setParam('LogFile', RESULTS_FOLDER + '/junk.txt') 
            
        if tune == 0 and folder != None:
            #do any necessary printing of pictures
            self._print_scenarios(printD, folder)
            
            #make the csv
            self._make_csv(folder)
            
        self._end_time = time.time()
        #don't have any return values, instead we can get the results from the class
        
    """
    get the result of the optimisation
    """
    def get_result(self):
        return self.m.objval
    
    """
    get a list of the actual moves that were made, returns a dictionary of the moves made
    at every stage in every turn
    each entry in the dictionary is a list of (square, tile) pairs
    """
    def get_moves_made(self):
        all_moves = {}
        #consider all moves, except for the original
        for c in self.C:
            if c != tuple():
                moves = []
                for s in self.I:
                    for t in self.T:
                        if self.X[t,s,c].x > 0.9:
                            moves.append((s,t))
                all_moves[c] = moves
        return all_moves
    
    """
    get the optimisation runtime of the operation
    """
    def get_gurobi_runtime(self):
        return round(self.m.runtime, 2)
    
    """
    get the total runtime of the solve operation
    """
    def get_total_runtime(self):
        return round(self._end_time - self._start_time, 2)
        
    """
    ensures that there is an empty folder located at 'folder', deleting any existing folder if there is one
    """        
    def _create_empty_folder(self, folder):

        #if the folder we are logging to exists, delete it
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass #if the folder wasn't there, we don't mind
        
        #then create an empty directory there, using makedirs to make any required folders along the way
        os.makedirs(folder)    

    """
    create all the sets used for the Railroad Ink problem
    """
    def _create_sets(self):
        self.I = {(i,j) for i in range(NUM_ROWS) for j in range(NUM_COLS)} #inside squares
        self.O = Board.get_start_squares() #outside squares
        self.S = self.I.union(self.O) #all squares
        
        self.T = Tile.get_all_variations() #all possible tiles
        self.E = [EdgeType.H, EdgeType.R] #the two edge types
        
        
        self.C = [] #every individual step of a scenario possible
        self.D = [] #all the final (Last) scenarios / dice rolls
        self._generate_scenarios([], self.D, self.C)   


    """
    create all the variables used in the Railroad Ink problem, if linear is True, then define the variables to
    form an LP else define them as integers
    """
    def _create_variables(self, linear):
        #unload the class variables into local variables for ease
        m = self.m
        T = self.T
        S = self.S
        C = self.C
        D = self.D
        E = self.E
        I = self.I
        O = self.O
        
        #BASIC PLACEMENT VARIABLES
        
        #x variables for whether tile t is placed at square s in the most recent turn of scenario c
        #x variables exist for every step of every scenario, which turn is defined by the length
        #of the tuple c, e.g if the tuple is () they are default placements, (1), they are first (since started)
        #move placements
        self.X = {(t,s,c) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) for t in T for s in S for c in C}
        #if linear:
        #    self.X = {(t,s,c) : m.addVar(ub=1) for t in T for s in S for c in C}
        #else:
        #    self.X = {(t,s,c) : m.addVar(vtype=GRB.BINARY) for t in T for s in S for c in C}
            
        #y variables for whether there is a link between adjacent squares with edge type e with dice rolls d
        #these variables are only calculated at the end of the scenarios, not during
        #for ease, create entries in the opposite direction that point to the same variables
        #e.g Y[s,ss,e,d] = Y[ss,s,e,d] for all values
            
        self.Y = {}
        for s in S:
            for e in E:
                for d in D:
                    for ss in self._board.adjacents(s, forward = True):
                        self.Y[s,ss,e,d] = m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1)
                        self.Y[ss,s,e,d] = self.Y[s,ss,e,d]
        
        #V is for whether there is a connection on each side  
        self.V = {(s,ss,e,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                for s in S for ss in self._board.adjacents(s) for e in E for d in D}

          
        #w variables are for any fake connections made
        if self._fake_connections:
            self.W = {(s,ss,e,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                    for s in S for ss in self._board.adjacents(s) for e in E for d in D}
            
        #z variables for how many open ends there are attached to any placed piece
        #only if we are adding points for open ends
        if self._open_ends:
            self.Z = {(s,ss,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                    for s in I for ss in self._board.adjacents(s, internal=True) for d in D}
            
        #r variables for the isolated placement removal flow problem
        if self._isolated_pieces == "relief":
            self.R = {(s,ss,c) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                    for s in S for ss in self._board.adjacents(s) for c in C if c != tuple()}
        
        #CONNECTING START POINTS VARIABLES
        if self._connecting_exits:
            #each of these is defined for every single possible set of dice rolls d in D
            #the flow problem is also defined for every start square 'o'
            #these are all linear variables since we start with only 1 as an input
            #the flow of joins between two adjacent squares
            self.F = {(s,ss,o,e,d): m.addVar() for s in S 
                    for ss in self._board.adjacents(s) for o in O for e in E for d in D}
            #transfer flow between rails and highways at square s (from e)
            self.FF = {(s,o,e,d) : m.addVar() for s in I for o in O for e in E for d in D} 
            
            #whether the extra point for connecting all of them is earned
            self.J = {d : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) for d in D}
            #flow from a start square to the super sink
            self.G = {(s,o,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) for s in O for o in O for d in D}   
                
            #Q variables are for the internal super sink connections, so any connection to the super sink can be via an internal edge
            #if that is an open end
            if self._internal_sinks:
                self.Q = {(s,ss,o,e,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                        for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D}
        
        #LONGEST RAILWAY/HIGHWAY VARIABLES
        if self._longest_paths:
            #each of these is defined for every single possible set of dice rolls d in D
            #whether square s is an end square of the path
            self.K = {(s,e,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                    for s in I for e in E for d in D}
                
            #whether there is a longest path connection between squares s and ss
            #define this similarly to the Y variables in that two references to the same variable exist
            self.L = {}
            for s in I:
                for e in E:
                    for d in D:
                        for ss in self._board.adjacents(s, forward = True, internal=True):
                            self.L[s,ss,e,d] = m.addVar()
                            self.L[ss,s,e,d] = self.L[s,ss,e,d]
            
            #whether square s counts towards the "e" longest road
            self.M = {(s,e,d) : m.addVar(vtype=(GRB.LINEAR if linear else GRB.BINARY), ub=1) 
                    for s in I for e in E for d in D}
            
            #relief flow problem, flow variables for ensuring that there is some flow to a start
            self.N = {(s,ss,e,d) : m.addVar()
                    for s in I for ss in self._board.adjacents(s, internal=True) for e in E for d in D}
            
        #SCORING VARIABLES
        #the score for every final scenario
        self.Alpha = {d : m.addVar() for d in D}

    """
    add all of the constraints to do with legal placements and setting of Y (connection) variables
    """
    def _legal_constraints(self):
        #unload the class variables into local variables for ease
        m = self.m
        T = self.T
        I = self.I
        S = self.S
        C = self.C
        D = self.D
        E = self.E
        V = self.V
        X = self.X
        Y = self.Y

        #only place one tile in each square - in all possible scenarios,
        #this means that only one tile can be placed there across all prefixes
        self.one_tile_per_square = {(s,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T for c in prefixes(d)) <= 1)
            for s in S for d in D}
            
        #ensure all the pieces that are already on the board are kept, and no others are placed
        #default placements have a scenario index of ()
        self.default_placements = {(t,s) :
            m.addConstr(X[t,s,()] == (1 if self._board.get_tile_at(s) == t else 0))
            for s in S for t in T}
            
        #on every turn, in every scenario, we can only use the moves that are allocated
        self.use_pieces = {(p,c) : 
            m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) <= 
                        (self._dice_rolls[len(c) - 1][c[-1]].get_dice().get(p, 0))) 
                        #^ this gets the dictionary of this dice roll, then searches for the piece, defaulting to zero
            for p in BASIC_PIECES + JUNCTION_PIECES + START_PIECES for c in C if c != tuple()}
    
        if self._specials:
            #play special pieces at most once each in every possible dice roll scenario
            self.special_once = {(p,d):
                    m.addConstr(quicksum(X[t,s,c] for s in S
                            for t in Tile.get_variations(p) for c in prefixes(d)) <= 1)
                    for p in SPECIAL_PIECES for d in D}
                
            #play at most one special piece per turn (in every scenario)
            self.one_special_per_turn = {c :
                m.addConstr(quicksum(X[t,s,c] for s in S for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=1)
                for c in C if c != tuple()}  
                
            #play max 3 special pieces total, for every single set of full dice rolls
            self.three_specials_max = {d :
                m.addConstr(quicksum(X[t,s,c] for s in S for c in prefixes(d)
                         for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=3)
                for d in D}
                
        else: #specials not played
            self.no_specials = m.addConstr(quicksum(X[t,s,c] for p in SPECIAL_PIECES for t in Tile.get_variations(p) 
                                                             for s in S for c in C if c != tuple()) == 0)
            
        #determine the V values, which are whether there is a route on a square on the edge of s that borders ss
        self.v_values = {(s,ss,e,d) :
            m.addConstr(V[s,ss,e,d] == quicksum(X[t,s,c] for c in prefixes(d) for t in T if t.get_edge_type_on_side(side) == e))
            for s in S for ss,side in self._board.adjacents_with_sides(s) for e in E for d in D}
        
        if self._fake_connections:
            W = self.W
            
            #cannot have any fake connections where a piece is already played
            self.invalid_ws = {(s,ss,e,d) :
                m.addConstr(W[s,ss,e,d] <= 1 - quicksum(X[t,s,c] for t in T for c in prefixes(d)))
                for s in S for ss in self._board.adjacents(s) for e in E for d in D}
                
            #cap the number of fake connections that can be made based on how many turns are remaining
            self.fake_connection_caps = {d :
                m.addConstr(quicksum(W[s,ss,e,d] for s in S for ss in self._board.adjacents(s) for e in E) <= self._fake_connections_max[self._end_turn_index])
                for d in D}
                
            #can have a connection on an edge from either side if there is a real placement or a fake placement
            self.connections = {(s,ss,e,d) :
                m.addConstr(Y[s,ss,e,d] <= V[s,ss,e,d] + W[s,ss,e,d])
                for s in S for ss,side in self._board.adjacents_with_sides(s) for e in E for d in D}
        else: 
            #can have a connection on an edge only if there is actually a connection there
            self.connections = {(s,ss,e,d) :
                m.addConstr(Y[s,ss,e,d] <= V[s,ss,e,d])
                for s in S for ss,side in self._board.adjacents_with_sides(s) for e in E for d in D}
            
        #constraints for clashes on edges joining squares horizontally, preventing railways and highways being connected
        #this needs to hold across every final scenario, only consider the final scenarios as the earlier ones are
        #accomplished using the final scenarios and are redundant to add
        self.horizontal_clashes = {(s,e,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e for c in prefixes(d)) +
                        quicksum(X[t,(s[0],s[1]+1),c] for t in T 
                            if t.get_edge_type_on_side(Side.LEFT) == EdgeType.clash_type(e) for c in prefixes(d)) <= 1)
            for s in S if (s[0],s[1]+1) in S for e in E for d in D}
            
        #constraints for clashes on edges joining squares vertically, preventing railways & highways connecting
        #scenario logic as for above constraints
        self.vertical_clashes = {(s,e,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e for c in prefixes(d)) +
                        quicksum(X[t,(s[0]+1,s[1]),c] for t in T if t.get_edge_type_on_side(Side.TOP) == EdgeType.clash_type(e) 
                                    for c in prefixes(d)) <= 1) 
            for s in S if (s[0]+1,s[1]) in S for e in E for d in D}
            
            
        #determine which constraints are being added based on how the isolated placements are being handled
        if self._isolated_pieces == "relief":
            R = self.R
            #we can have a relief connection from any piece played on this turn with a connection on that edge
            self.relief_connections_1 = {(s,ss,c):
                m.addConstr(R[s,ss,c] <= 5*quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(side) != EdgeType.B))
                for s in S for ss,side in self._board.adjacents_with_sides(s) for c in C if c != tuple()}
            #we can have a relief connection to any piece played with a connection on that edge on this turn or earlier
            self.relief_connections_2 = {(s,ss,c):
                m.addConstr(R[s,ss,c] <= 5*quicksum(X[t,ss,cc] for cc in prefixes(c) 
                                         for t in T if t.get_edge_type_on_side(Side.opposite(side)) != EdgeType.B))
                for s in S for ss,side in self._board.adjacents_with_sides(s) for c in C if c != tuple()}
                
            self.relief_flow = {(s,c):
                m.addConstr(quicksum(X[t,s,c] for t in T) + quicksum(R[ss,s,c] for ss in self._board.adjacents(s)) <=
                            quicksum(R[s,ss,c] for ss in self._board.adjacents(s)) + 5*quicksum(X[t,s,cc] for t in T for cc in prefixes(c) if c != cc))
                for s in S for c in C if c != tuple()}
        else:
            #any played piece must be connected to a piece played earlier or on this turn
            self.earlier_move_connection = {}
            for t in T:
                adj = {}
                for side in Side:
                    adj[side] = []
                    etype = t.get_edge_type_on_side(side)
                    if etype != EdgeType.B:
                        oppSide = Side.opposite(side)
                        for tt in T:
                            if tt.get_edge_type_on_side(oppSide) == etype:
                                adj[side].append(tt)
                for s in S:
                    connections = []
                    for side in Side:
                        oppS, oppSide = self._board.opposite_edge(s, side)
                        if self._board.get_tile_at(oppS) != None:
                            for tt in adj[side]:
                                connections.append((oppS,tt))
                    for c in C:
                        if c != tuple():
                            self.earlier_move_connection[t,s,c] = m.addConstr(X[t,s,c] 
                                    <= quicksum(X[tt,ss,cc] for (ss,tt) in connections for cc in prefixes(c)))
                        
                        
        #detection of open ends
        if self._open_ends:
            Z = self.Z
            #only have an open end if there is an edge on that side
            self._open_end_scoring_1 = {(s,ss,d):
                m.addConstr(Z[s,ss,d] <=  quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(side) != EdgeType.B for c in prefixes(d)))
                for s in I for ss,side in self._board.adjacents_with_sides(s, internal=True) for d in D}           
              
            #not an open end if there is anything on the other side
            self._open_end_scoring_2 = {(s,ss,d): 
                m.addConstr(Z[s,ss,d] <= 1 - quicksum(X[t,ss,c] for t in T for c in prefixes(d)))
                for s in I for ss in self._board.adjacents(s,internal=True) for d in D}

    """
    constraints for joining exits
    """
    def _joining_exits_constraints(self):
        #unload the class variables into local variables for ease
        m = self.m
        T = self.T
        S = self.S
        C = self.C
        D = self.D
        E = self.E
        I = self.I
        O = self.O
        V = self.V
        X = self.X
        Y = self.Y
        F = self.F
        FF = self.FF
        G = self.G
        J = self.J
        
        #these are all done for only the complete dice rolls, so for d in D
        #the internal constraints also exist for every possible origin square o in O
        
        #the flow into an internal square must be the same as the flow out
        if not self._internal_sinks:
            self.internal_flows = {(s,o,e,d) :
                m.addConstr(quicksum(F[s,ss,o,e,d] for ss in self._board.adjacents(s)) + FF[s,o,e,d] ==
                            quicksum(F[ss,s,o,e,d] for ss in self._board.adjacents(s)) + FF[s,o,EdgeType.clash_type(e),d])
                for s in I for o in O for e in E for d in D}
            
            #the flow into an external square must be the same as the flow out
            #these have a guaranteed flow in of 1 when we are at the origin of this flow problem o
            #they also have the ability to flow out to the sink with variable G
            self.external_flows = {(s,o,d) :
                m.addConstr((1 if s == o else 0) + quicksum(F[ss,s,o,e,d] for ss in self._board.adjacents(s) for e in E) ==
                        quicksum(F[s,ss,o,e,d] for ss in self._board.adjacents(s) for e in E) + G[s,o,d])
                for s in O for o in O for d in D}
        else:
            Q = self.Q #get the dictionary with the Q variables for internal super sink connections
            #we can also flow out via an internal sink connection
            self.internal_flows = {(s,o,e,d) :
                m.addConstr(quicksum(F[s,ss,o,e,d] + Q[s,ss,o,e,d] for ss in self._board.adjacents(s)) + FF[s,o,e,d] ==
                            quicksum(F[ss,s,o,e,d] for ss in self._board.adjacents(s)) + FF[s,o,EdgeType.clash_type(e),d])
                for s in I for o in O for e in E for d in D}
                
            self.external_flows = {(s,o,d) :
                m.addConstr((1 if s == o else 0) + quicksum(F[ss,s,o,e,d] for ss in self._board.adjacents(s) for e in E) ==
                        quicksum(F[s,ss,o,e,d] + Q[s,ss,o,e,d] for ss in self._board.adjacents(s) for e in E) 
                        + G[s,o,d])
                for s in O for o in O for d in D}
                
            #we can only flow out along an edge with a connection
            self.internal_sink_connections_1 = {(s,ss,o,e,d) :
                m.addConstr(Q[s,ss,o,e,d] <= V[s,ss,e,d])
                for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D}
            
            #there mustn't be any other piece on the opposite side of this connection though
            self.internal_sink_connections_2 = {(s,ss,o,e,d) :
                m.addConstr(Q[s,ss,o,e,d] <= 1 - quicksum(X[t,ss,c] for t in T for c in prefixes(d)))
                for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D}
            

               
        #flow variables can only be set if the connection exists on that edge
        self.flow_existence = {(s,ss,o,e,d):
            m.addConstr(F[s,ss,o,e,d] <= Y[s,ss,e,d])
            for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D}
            
        #transfer flow existence, if the piece played is a junction, we can flow between highways and railways on that square
        self.transfer_flow = {(s,o,e,d):
            m.addConstr(FF[s,o,e,d] <= quicksum(X[t,s,c] for t in T if t.get_piece() in SWITCH_PIECES for c in prefixes(d)))
            for s in I for o in O for e in E for d in D}
            
        #only allow flow in one direction between every pair of exits
        self.unidrectional_flow = {(s,o,d) :
            m.addConstr(G[s,o,d] == 0)
            for s in O for o in O if s < o for d in D}
            
        #this is a redundant constraint, but might help simplify things a bit
        #basically saying don't look around to flow into 2 places, it's impossible
        self.one_outflow = {(o,d):
            m.addConstr(quicksum(G[s,o,d] for s in O) <= 1)
            for o in O for d in D}
            
        #add a bonus point if there is only one connection to the super sink (all exits connected)
        self.bonus_point = {d :
            m.addConstr((NUM_STARTS - 1)*J[d] <= quicksum(G[s,o,d] for s in O for o in O if s != o))
            for d in D}
            
        #if it is turn 1, reduce symmetry by forcing the top left to have more pieces
        if self._turn == 1:
            self._symmetry_removal = {
                    m.addConstr(quicksum(X[t,(row,col),c] for row in range(3) for col in range(3) for t in T ) >=
                                quicksum(X[t,(row,col),c] for row in range(rS, rS+3) for col in range(cS, cS+3) for t in T ))
                    for (rS, cS) in [(0,4),(4,0),(4,4)] for c in C if len(c) == 1}
            
#        self.transitivity_removal = {(s, ss, sss) :
#            m.addConstr(G[ss,s,d] <= 1 - G[sss,ss,d])
#            for s in O for ss in O for sss in O for d in D if s < ss and ss < sss}

    """
    constraints for defining the longest paths (railway/highway)
    """
    def _longest_path_constraints(self):
        #unpack some class variables into local variables to make the constraints cleaner
        m = self.m
        I = self.I
        E = self.E
        D = self.D
        Y = self.Y
        K = self.K
        L = self.L
        M = self.M
        N = self.N
        
        #these are only calculated for the full scenarios, for d in D
        
        #there must be two starting points and only 2 starting points
        #the only time this would not be 2 is if there are no length 2 paths on the board
        self.two_ends = {(e,d) :
            m.addConstr(quicksum(K[s,e,d] for s in I) <= 2)
            for e in E for d in D}
            
        #an edge can only score points if it is a start square and has one out connection or has two directional connections
        self.inflow = {(s,e,d) :
            m.addConstr(2*M[s,e,d] == K[s,e,d] + quicksum(L[s,ss,e,d] for ss in self._board.adjacents(s, internal=True)))
            for s in I for e in E for d in D}
            
        #the score at a square must be greater than the flow in on every edge, this prevents lopsided scores in the LP
        #this constraint actually forces the entire problem to be an LP (except for handling loops)
        #this hopefully dramatically tightens the LP solution
        self.lp_constraints = {(s,ss,e,d) :
            m.addConstr(M[s,e,d] >= L[s,ss,e,d])
            for s in I for ss in self._board.adjacents(s, internal=True) for e in E for d in D}
            
        #only let an edge be travelled on if there is another input to the tile as well,
        #this is kind of redundant given the above constraint, but does seem to speed it up a bunch, probably need
        #more data to determine if it's worth including
        self.lp_constraints_2 = {(s,ss,e,d) :
            m.addConstr(L[s,ss,e,d] <= K[s,e,d] + quicksum(L[s,sss,e,d] for sss in self._board.adjacents(s, internal=True) if ss != sss))
            for s in I for ss in self._board.adjacents(s, internal=True) for e in E for d in D}
            
        #size 4 loop constraints for the LP, cuts off loops 
        self.lp_constraints_3 = {((r,c),e,d) :
            m.addConstr((3/4)*(M[(r,c),e,d] + M[(r,c+1),e,d] + M[(r+1,c),e,d] + M[(r+1,c+1),e,d]) >=
                        L[(r,c),(r,c+1),e,d] + L[(r,c),(r+1,c),e,d] +
                        L[(r,c+1),(r+1,c+1),e,d] + L[(r+1,c),(r+1,c+1),e,d])
            for r in range(NUM_ROWS-1) for c in range(NUM_COLS-1) for e in E for d in D}
            
        #there can only be flow on edges that have a connection of that type
        self.only_on_connected_edges = {(s,ss,e,d) :
            m.addConstr(L[s,ss,e,d] <= Y[s,ss,e,d])
            for s in I for ss in self._board.adjacents(s, internal=True, forward=True) for e in E for d in D}

        #remove all size 4 loops by default, unneccessary but should help a bit
#        self.no_size_4_loops = {((r,c),e,d) :
#            m.addConstr(L[(r,c),(r,c+1),e,d] + L[(r,c),(r+1,c),e,d] +
#                        L[(r,c+1),(r+1,c+1),e,d] + L[(r+1,c),(r+1,c+1),e,d] <= 3)
#            for r in range(NUM_ROWS-1) for c in range(NUM_COLS-1) for e in E for d in D}
            
        #don't set a start location and not have it scoring, this may be redundant with the two_ends equality
        self.end_bounds = {(s,e,d) :
            m.addConstr(K[s,e,d] <= M[s,e,d])
            for s in I for e in E for d in D}
            
        #relief constraints
        self.path_relief = {(s,e,d) :
            m.addConstr(quicksum(N[s,ss,e,d] for ss in self._board.adjacents(s, internal=True)) + 16 * K[s,e,d] >=
                        quicksum(N[ss,s,e,d] for ss in self._board.adjacents(s, internal=True)) + M[s,e,d])
            for s in I for e in E for d in D}
            
        self.path_relief_on_edges = {(s,ss,e,d) :
            m.addConstr(N[s,ss,e,d] <= 16 * L[s,ss,e,d])
            for s in I for ss in self._board.adjacents(s, internal=True) for e in E for d in D}
            

    """
    constraints for the scoring of the board
    """
    def _scoring_constraints(self):
        #unpack some variables to make the constraint cleaner
        m = self.m
        I = self.I
        O = self.O
        T = self.T
        E = self.E
        D = self.D
        X = self.X
        Y = self.Y
        Alpha = self.Alpha
        if self._connecting_exits:
            G = self.G
            J = self.J
        if self._longest_paths:
            M = self.M
        
        #calculate the score for each full scenario, use a <= because the optimisation will force equality where important
        self.scoring = {d :
            m.addConstr(Alpha[d] <= quicksum(X[t,s,c] for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)) #centre square points
                                  + (4 * quicksum(G[s,o,d] for s in O for o in O if s != o) + J[d] if self._connecting_exits else 0) #connecting exits points
                                  + (quicksum(M[s,e,d] for s in I for e in E) if self._longest_paths else 0) #longest path points
                                  - (quicksum(X[t,s,c] * t.loose_ends(s) for t in T for s in I for c in prefixes(d)) #subtraction for the number of loose ends (start of penalty calculation)
                                  - quicksum(Y[s,ss,e,dd] for (s,ss,e,dd) in Y if dd == d and s in I and ss in I) #these points are not lost if there is a join on that edge
                                          if self._errors else 0)
            )
            for d in D}

    """
    set the objective function of the model, this depends on what the objective function was selected as
    """
    def _set_objective(self):
        #unpack into local variables to make naming cleaner
        m = self.m
        D = self.D
        I = self.I
        O = self.O
        S = self.S
        E = self.E
        Alpha = self.Alpha
        
        if self._objective == "expected-score":
            #m.setObjective(quicksum(Alpha[d] * self._scenario_probability(d) for d in D), GRB.MAXIMIZE)
            #score regularly but give some extra points for any open ends according to the scoring array
            m.setObjective(quicksum((Alpha[d] 
                                    + (quicksum(self.Z[s,ss,d] for s in I for ss in self._board.adjacents(s, internal=True)) * self._open_end_points[self._end_turn_index] 
                                             if self._open_ends else 0)
                                    + (quicksum(self.Q[s,ss,o,e,d] for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D) * self._internal_sink_scores[self._end_turn_index]
                                            if self._internal_sinks else 0)
                                    - (quicksum(self.W[s,ss,e,d] for s in S for ss in self._board.adjacents(s) for e in E for d in D) * self._fake_connections_cost[self._end_turn_index]
                                             if self._fake_connections else 0)) 
                                    * self._scenario_probability(d) for d in D), GRB.MAXIMIZE)
            
        
       
    """
    get the probability of a specific scenario, d
    """
    def _scenario_probability(self, d):
        prob = 1
        for turn, roll_num in enumerate(d):
            prob *= self._dice_rolls[turn][roll_num].get_probability()
        return prob


    """
    set the parameters for Gurobi to use for the solve
    """
    def _set_gurobi_parameters(self, seed, folder, tune, lazy_constraints):
        self.m.setParam('Seed',seed)
        if tune == 0:
            if lazy_constraints:
                self.m.setParam('LazyConstraints', 1)
            #self.m.setParam('MIPGap', 0)
            #self.m.setParam('BranchDir', 1)
            self.m.setParam('Heuristics', 0.001)
            self.m.setParam('Cuts', 1)
            self.m.setParam('GomoryPasses', 0)
        else:
            self.m.setParam('TuneTimeLimit', tune)
        if folder != None:
            self.m.setParam('LogFile', folder + "/log.txt")
        
        
        


    #############################PRINTING######################################
    
    """
    determine where to print stdout to depending on whether or not we want to see it
    if printOutput is True, returns stdout, if False returns a fake printer that does nothing
    """
    def _print_stream_location(self, printOutput):
        #set up where to print to
        if printOutput == True:
            return sys.stdout #continue printing to stdout
        else:
            return EmptyPrinter() #print to my terrible printer that doesn't do anything

    """
    prints all scenarios listed in printD, if printD == "all", then prints all scenarios in D to folder
    """
    def _print_scenarios(self, printD, folder):
        if printD == "all": #if the argument was "all" then print all scenarios
            printD = self.D

        #save them all with different names in the given folder, this folder must exist
        for d in printD:
            self._print_scenario(d, folder)
     
    
    """
    print the board with the solution attached for a given scenario d
    """
    def _print_scenario(self, d, folder):
        #find all the pieces and placements that we made and add them to the board
        added_squares = [] #track the squares that were added
        for s in self.S:
            for t in self.T:
                for c in prefixes(d):
                    if c != tuple() and self.X[t,s,c].x > 0.9:
                        self._board.add_tile(t, s, self._turn - 1 + len(c))
                        added_squares += [s]
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print("{0}/solution {1}.png".format(folder, d))
        #remove all the squares from the board in case we need to print another situation
        for s in added_squares:
            self._board.remove_tile(s)
            
    """
    creates a csv in the correct folder with all information about the scoring
    """       
    def _make_csv(self, folder):
        #unpack some variables
        I = self.I
        O = self.O
        S = self.S
        T = self.T
        D = self.D
        E = self.E
        X = self.X
        Y = self.Y
        C = self.C
        if self._connecting_exits:
            G = self.G
            J = self.J
        if self._longest_paths:
            M = self.M
        
        Alpha = self.Alpha
        
        #print the results to a CSV
        resultsFile = folder + "/" + RESULTS_CSV
        with open(resultsFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            title_row = ["Turn {0}".format(self._turn + i) for i in range(len(self._dice_rolls))]
            title_row += ["Score", "Connecting Exits", "Longest Railway", "Longest Highway", "Centre Points", "Errors", "Bonus Point"]
            title_row += ["Open Ends"] if self._open_ends else []
            title_row += ["Fake Connections"] if self._fake_connections else []
            title_row += ["Internal Sink Points"] if self._internal_sinks else []
            csv_writer.writerow(title_row)
            for d in D:
                #do the calculations
                score = round(Alpha[d].x)
                centre_points = round(sum(X[t,s,c].x for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d))) 
                connecting_points = (round(4 * sum(G[s,o,d].x for s in O for o in O if s != o)) if self._connecting_exits else 0)
                longest_railway = (round(sum(M[s,EdgeType.R,d].x for s in I)) if self._longest_paths else 0)
                longest_highway = (round(sum(M[s,EdgeType.H,d].x for s in I)) if self._longest_paths else 0)
                errors_points = (round(-1* sum(X[t,s,c].x * t.loose_ends(s) for t in T for s in I for c in prefixes(d))
                              + sum(Y[s,ss,e,dd].x for (s,ss,e,dd) in Y if dd == d and s in I and ss in I))
                                if self._errors else 0)
                bonus_point = round(J[d].x) if self._connecting_exits else 0
                score_row = [turn for turn in d] + [score, connecting_points, longest_railway, 
                                                            longest_highway, centre_points, errors_points, bonus_point]
                if self._open_ends:
                    Z = self.Z
                    open_ends = round(sum(Z[s,ss,d].x for s in I for ss in self._board.adjacents(s, internal=True)) * self._open_end_points[self._end_turn_index],2)
                    score_row += [open_ends]
                    
                if self._fake_connections:
                    connections_score = round(sum(self.W[s,ss,e,d].x for s in S for ss in self._board.adjacents(s) for e in E) * self._fake_connections_cost[self._end_turn_index],2)
                    score_row += [connections_score]
                    
                if self._internal_sinks:
                    internal_sinks_score = round(sum(self.Q[s,ss,o,e,d].x for s in S for ss in self._board.adjacents(s) for o in O for e in E) * self._internal_sink_scores[self._end_turn_index],1)
                    score_row += [internal_sinks_score]
                csv_writer.writerow(score_row)
    
        #also create a csv for the moves that were made
        movesFile = folder + "/" + MOVES_CSV
        with open(movesFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            for c in C:
                csv_writer.writerow(["Scenario {0}".format(c)])
                for s in S:
                    for t in T:
                        if X[t,s,c].x > 0.9:
                            csv_writer.writerow([t.get_piece(), t.get_rotation(), t.get_flip(), s[0], s[1]])
        
        
    #############################CALLBACK FUNCTIONS############################
        
    """
    The callback used in the Railroad Ink solver
    """    
    def _callback(self, model, where):
        if where == GRB.Callback.MIPSOL:
            #get the X and L values in the solution
            XV = {k : v for (k,v) in zip(self.X.keys(), model.cbGetSolution(list(self.X.values())))}
            if self._longest_paths:
                LV = {k : v for (k,v) in zip(self.L.keys(), model.cbGetSolution(list(self.L.values())))}
            else:
                LV = {} #won't be needed at all
            #run the lazy checks for every first dice roll considered
            for first_dice_roll in range(len(self._dice_rolls[0])):
                self._lazy_checks((first_dice_roll,), XV, LV)
            
    """
    find the pieces that are missing given the played tiles and the expected count for pieces
    """
    def _find_missing_pieces(self, playedTiles, expectedPieceCounts):
        #next check using the played tiles that enough have been played
        answerCounts = {}
        for tile, square in playedTiles:
            answerCounts[tile.get_piece()] = answerCounts.get(tile.get_piece(),0) + 1
            
        #check through and ensure enough have been played and track any pieces that are missing
        missingPieces = []
        for piece in expectedPieceCounts:
            if expectedPieceCounts[piece] > answerCounts.get(piece,0):
                missingPieces += [piece]
        return missingPieces
    
    """
    returns True if the placement of tile at square s is a valid move on the board,
    i.e connects to an existing piece without any clashes
    """
    def _valid_placement(self, tile, s):
        #a placement is valid if there is any connection to another piece and no invalid connections
        connections = 0
        for side in Side:
            newEdgeType = tile.get_edge_type_on_side(side)
            #check if that side is blank
            if newEdgeType != EdgeType.B:
                #get the opposite side
                oppS, oppSide = Board.opposite_edge(s,side)
                #now check if the opposite side exists and if there is a connection or a clash there
                if oppS in self.S:
                    existingEdgeType = self._board.get_tile_at(oppS).get_edge_type_on_side(oppSide)
                    if existingEdgeType == newEdgeType:
                        connections += 1
                    elif existingEdgeType == EdgeType.clash_type(newEdgeType):
                        return False #there is a clash, we cannot play this piece here
        return (connections > 0) #we can play a piece if there was at least one connection, otherwise we can't
    
    
    """
    returns True if one of the missingPieces can be played on the board, False if they cannot
    """
    def _can_place_a_missing_piece(self, missingPieces):
        #now for every missing piece, we need to check if there is absolutely anywhere it could go
        for piece in missingPieces:
            variations = Tile.get_variations(piece) #get the possible orientations
            #check to see if there is anywhere this piece could be placed
            for s in self.I:
                if self._board.is_square_free(s):
                    #check every variation of the tile
                    for tile in variations:
                        #if this placement is valid, then there is a valid placement
                        if self._valid_placement(tile, s):
                            return True           
        return False #we found no placement for any missing piece
                                    
    """
    determines if there are any loops in this solution and adds lazy constraints if there are any
    d is the scenario of dice rolls we received
    """
    def _add_any_loop_lazy_constraints(self, d, LV):
        #unpack some variables
        m = self.m
        E = self.E
        L = self.L
        M = self.M
        
        
        if len(d) == len(self._dice_rolls): #we are on the final roll
            #use the existing board and check for loops, start by looking for any top left corners, as every loop has to have 
            #a top left connection both to the right and down from one square
            for r in range(NUM_ROWS - 1): #cannot have a loop starting in the last row (or col)
                for c in range(NUM_COLS - 1):
                    for e in E:
                        if LV[(r,c),(r+1,c),e,d] > 0.9 and LV[(r,c),(r,c+1),e,d] > 0.9:
                            #follow this path for as long as possible, starting going right
                            current_r = r
                            current_c = c + 1
                            previous_dir = (0,1)
                            squares = [(r,c)] #the list of all squares seen on this path
                            while True:
                                squares += [(current_r, current_c)]
                                if current_r == r and current_c == c: #we have got back to the start, this is a loop
                                    #add a lazy constraint to say that this path cannot be entirely on
                                    m.cbLazy(((len(squares)-2)/(len(squares)-1))*quicksum(M[squares[i],e,d] for i in range(len(squares)-1)) >= 
                                            quicksum(L[squares[i],squares[i+1],e,d] for i in range(len(squares)-1)))
                                    break #leave the while loop, we have found a loop
                                #consider all of the directions we could be travelling, it can only be one of these
                                for (dr,dc) in [(0,1),(1,0),(0,-1),(-1,0)]:
                                    #if we aren't retracing and can continue in the given direction, move that direction
                                    if tuple(np.add(previous_dir, (dr,dc))) != (0,0) and Board.square_internal(current_r + dr, current_c + dc) and \
                                            LV[(current_r,current_c),(current_r+dr,current_c+dc),e,d] > 0.9:
                                        current_r += dr
                                        current_c += dc
                                        previous_dir = (dr,dc) #track which direction we went last
                                        break; #we can only move in one direction, breaking also confirms we moved for the else
                                else: #there was no break, i.e we didn't move anywhere
                                    break #break out of the while loop, we ran into a dead end
    
    """
    adds any required lazy constraints for isolated placements
    returns True if any have been added, False otherwise
    """
    def _add_any_isolated_placement_lazy_constraints(self, scenario, playedTiles):
        m = self.m
        S = self.S
        T = self.T
        X = self.X
        
        #check if the played tiles are valid placements, i.e have connections to the board
        tilesToAdd = list(playedTiles) #copy the played tiles to a list for adding to the board
        #iterate through the list of played tiles, adding any connecting to the board to the board,
        #iterate until there is a run where no tiles are added
        anyAdds = True
        while anyAdds:
            anyAdds = False
            i = 0 #use an indexed while loop instead of a for loop since we are removing elements
            while i < len(tilesToAdd):
                tile, s = tilesToAdd[i]
                if self._valid_placement(tile, s):
                    #if this is a valid placement on the board, add it to the board and remove it from the 
                    #list of tiles we need to add
                    self._board.add_tile(tile, s)
                    tilesToAdd.pop(i)
                    anyAdds = True 
                else:
                    i += 1
                    
        #if not all of the tiles were added, it means there were some isolated placements
        if len(tilesToAdd) != 0:
            #there were some isolated placements, these must be removed
            #either by removing one of the isolated placements 
            #or by placing a piece connecting to them
            isolatedSquares = [s for (tile,s) in tilesToAdd]
            
            #look for any square-side-edgeType combinations that could be used to save it
            connectionPoints = []
            for tile, square in tilesToAdd:
                for side in Side:
                    if tile.get_edge_type_on_side(side) != EdgeType.B:
                        oppS, oppSide = Board.opposite_edge(square, side)
                        #if the opposite side could have a rail-highway connection and isn't one of the isolated squares
                        #then add it as a potential location to connect to
                        if oppS in S and oppS not in isolatedSquares:
                            connectionPoints += [(oppS, oppSide, tile.get_edge_type_on_side(side))]
            
            m.cbLazy(1 <= quicksum(1 - X[t,s,scenario] for (t,s) in tilesToAdd) #can remove an isolated tile
                            + quicksum(X[t,s,c] for (s, side, edgeType) in connectionPoints  #all connection pieces on any prior scenario
                                                for c in prefixes(scenario) if c != tuple()
                                                for t in T if t.get_edge_type_on_side(side) == edgeType))
            #then add these to the board when checking for if pieces are missing
            for tile, s in tilesToAdd:
                self._board.add_tile(tile, s)
            #set a flag for if there were isolated placements
            return True
        else:
            return False
    
    
    """
    Do the checks for adding lazy constraints,
    this is a recursive function, if the checks for one step of the scenario pass, then it is called for all children of
    that scenario
    """        
    def _lazy_checks(self, scenario, XV, LV):
        #unpack some needed variables
        m = self.m
        I = self.I
        X = self.X #retrieve the X variables
        
        #find the pieces that need to be played in this scenario and the corresponding tiles
        pieceCounts = self._dice_rolls[len(scenario)-1][scenario[-1]].get_dice()
        tilesToCheck = []
        for piece in pieceCounts:
            tilesToCheck += Tile.get_variations(piece)
        for piece in SPECIAL_PIECES:
            tilesToCheck += Tile.get_variations(piece)
        
        #search through the current solution to see which pieces have been played
        playedTiles = []
        for s in I:
            for tile in tilesToCheck:
                if XV[tile,s,scenario] > 0.9:
                    playedTiles += [(tile,s)]
        
        if self._isolated_pieces == "lazy":            
            isolatedPieces = self._add_any_isolated_placement_lazy_constraints(scenario, playedTiles)
        else:
            isolatedPieces = False
                                                
        #if there were no isolated pieces, then all pieces were added to the board in the earlier process
        missingPieces = self._find_missing_pieces(playedTiles, pieceCounts)
        
        canPlaceMissingPiece = self._can_place_a_missing_piece(missingPieces)
        if canPlaceMissingPiece:
            m.cbLazy(1 <= quicksum(1 - X[t,s,scenario] for (t,s) in playedTiles) #we can move an already played tile
                            + quicksum(X[t,s,scenario] for piece in missingPieces for t in Tile.get_variations(piece) 
                                    for s in I if self._board.get_piece_at(s) == Piece.BLANK) #play a missing piece
                            + (quicksum(X[t,s,scenario] for piece in SPECIAL_PIECES for t in Tile.get_variations(piece) for s in I) 
                                    if not self._board.all_specials_used() else 0)) #play a special piece
         
        #finally we also want to check for any loops for longest paths
#        if self._longest_paths:
#            self._add_any_loop_lazy_constraints(scenario, LV)
            
        #if we haven't added any lazy constraints for this scenario, do the checks for all the child scenarios
        if not canPlaceMissingPiece and not isolatedPieces and len(scenario) < len(self._dice_rolls):
            for nextRoll in range(len(self._dice_rolls[len(scenario)])):
                self._lazy_checks(scenario + (nextRoll,), XV, LV)
            
        #remove the tiles from the board
        for tile, square in playedTiles:
            self._board.remove_tile(square)
    
"""
there may well be a better way of doing this, but Gurobi needs to have somewhere to "print" to,
so if we don't want to print to stdout at all, we need to redirect stdout to something, not nothing, 
and this is the most nothing something I could think of
"""
class EmptyPrinter:
    def write(*args):
        pass
    
    def flush(*args):
        pass
    
        
if __name__ == "__main__":
#    board = rulebook_game()
#    dice_rolls = rulebook_dice_rolls()
#    s = RailroadInkSolver(board, 7, dice_rolls, "expected-score", fake_connections=True)
#    s.solve(folder="rulebook", printOutput=True, printD="all")
    
    #board = Board()
#    dice_rolls = [[DiceRoll({Piece.RAILWAY_STRAIGHT : 1}, 1)],
#                   [DiceRoll({Piece.RAILWAY_STRAIGHT : 1}, 1)]]
#    #s = RailroadInkSolver(board, 1, dice_rolls, "open-ends", specials=False, isolated_pieces="relief")
#    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", specials=False, isolated_pieces="relief")
#    s.solve(folder="test", printOutput=True, printD="all")

#    board = Board()
#    
##    dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
##                             Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
##                  [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
##                             Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 1)]]
#    
#    dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
#                             Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
#                  [DiceRoll({Piece.RAILWAY_STRAIGHT : 1}, 1.0/9),
#                   DiceRoll({Piece.RAILWAY_CORNER : 1}, 1.0/9),
#                   DiceRoll({Piece.RAILWAY_T : 1}, 1.0/9),
#                   DiceRoll({Piece.HIGHWAY_STRAIGHT : 1}, 1.0/9),
#                   DiceRoll({Piece.HIGHWAY_CORNER : 1}, 1.0/9),
#                   DiceRoll({Piece.HIGHWAY_T : 1}, 1.0/9),
#                   DiceRoll({Piece.STRAIGHT_STATION : 1}, 1.0/9),
#                   DiceRoll({Piece.CORNER_STATION : 1}, 1.0/9),
#                   DiceRoll({Piece.OVERPASS : 1}, 1.0/9)]]
#    
#    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", specials=False, isolated_pieces="relief")
#    s.solve(folder="test", printOutput=True, printD="all")  
    
    
    
    board = Board()
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,0), 3)
    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 3)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,2), 4)
    board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R180), (1,3), 4)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (2,1), 2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (2,3), 5)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,0), 2)
    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,1), 2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (3,2), 3)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,6), 4)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (4,2), 3)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R180, flip=False), (4,3), 4)
    board.add_tile(Tile(Piece.HIGHWAY_JUNCTION, Rotation.I), (4,4), 5)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,0), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (5,1), 1)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.I, flip=True), (5,2), 2)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (5,3), 4)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,6), 5)
    board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (6,1), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (6,3), 1)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (6,4), 5)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270, flip=False), (6,5), 5)
    
    dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
                             Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)]]
    
    #dice_rolls = [[DiceRoll({}, 1)]]

    #s = RailroadInkSolver(board, 6, dice_rolls, "expected-score", internal_sinks=True)
    s = RailroadInkSolver(board, 6, dice_rolls, "expected-score")
    s.solve(printOutput=True, printD="all")