
from gurobipy import Model, GRB, quicksum
from gurobipy import *
from board import Board, Tile, Side, EdgeType, NUM_ROWS, NUM_COLS
from board import *
import csv
import numpy as np
import os
import shutil
import sys
import contextlib
import time

RESULTS_FOLDER = "results"
CSV_NAME = "points.csv"


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
    """
    def __init__(self, board, turn, dice_rolls, objective):
        self._board = board
        self._turn = turn
        self._dice_rolls = dice_rolls
        self._objective = objective
    
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
            saves to "last-run" if no folder is specified
    linear - if True, runs an LP, if False runs the IP
    printOutput - whether to print Gurobi output to stdout
    printPictures - whether to print the pictures directly, if False, prints any selected pictures to the folder
    printD - a list of scenarios to print, or "all" if all scenarios should be printed, default is to not print
    seed - the seed to use for gurobi
    """
    def solve(self, folder="last-run", linear=False, printOutput=False, printPictures=False, printD=[], seed=0):
        
        self._start_time = time.time()
        
        folder = RESULTS_FOLDER + "/" + folder #update the folder name, always in the RESULTS top folder
        
        #create an empty folder to store all the results in
        self._create_empty_folder(folder)
        
        #create the model
        self.m = Model("Railroad Ink")
        
        self._create_sets()
        
        self._create_variables(linear)
        
        self._legal_constraints()
        self._joining_exits_constraints()  
        self._longest_path_constraints()
        self._scoring_constraints()
        
        self._set_objective()
        
        #for some reason defining the callback in this function is the only way I seem to be able
        #to get the callback to play with Python's classes
        def Callback(model, where):
            self._callback(model, where)

        #redirect all output in this context, potentially to nowhere if we are not printing to stdout
        with contextlib.redirect_stdout(self._print_stream_location(printOutput)):
            self._set_gurobi_parameters(seed, folder)
            
            #OPTIMIZE
            self.m.optimize(Callback)
        
            #all logging is over, point the logfile somewhere else
            #this removes Gurobi's reference to the needed file so that it can be deleted
            self.m.setParam('LogFile', RESULTS_FOLDER + '/junk.txt') 
            
        #do any necessary printing of pictures
        self._print_scenarios(printD, printPictures, folder)
        
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
        if linear:
            self.X = {(t,s,c) : m.addVar(ub=1) for t in T for s in S for c in C}
        else:
            self.X = {(t,s,c) : m.addVar(vtype=GRB.BINARY) for t in T for s in S for c in C}
            
        #y variables for whether there is a link between adjacent squares with edge type e with dice rolls d
        #these variables are only calculated at the end of the scenarios, not during
        #for ease, create entries in the opposite direction that point to the same variables
        #e.g Y[s,ss,e,d] = Y[ss,s,e,d] for all values
        self.Y = {}
        for s in S:
            for e in E:
                for d in D:
                    for ss in self._board.adjacents(s, forward = True):
                        self.Y[s,ss,e,d] = m.addVar()
                        self.Y[ss,s,e,d] = self.Y[s,ss,e,d]
        
        #CONNECTING START POINTS VARIABLES
        
        #each of these is defined for every single possible set of dice rolls d in D
        #the flow problem is also defined for every start square 'o'
        #these are all linear variables since we start with only 1 as an input
        #the flow of joins between two adjacent squares
        self.F = {(s,ss,o,e,d): m.addVar() for s in S 
                for ss in self._board.adjacents(s) for o in O for e in E for d in D}
        #transfer flow between rails and highways at square s (from e)
        self.FF = {(s,o,e,d) : m.addVar() for s in I for o in O for e in E for d in D} 
        #flow from a start square to the super sink
        self.G = {(s,o,d) : m.addVar() for s in O for o in O for d in D} 
        #whether the extra point for connecting all of them is earned
        if linear:
            self.J = {d : m.addVar(ub=1) for d in D}
        else:
            self.J = {d : m.addVar(vtype=GRB.BINARY) for d in D}
        
        #LONGEST RAILWAY/HIGHWAY VARIABLES
        
        #each of these is defined for every single possible set of dice rolls d in D
        #whether square s is an end square of the path
        self.K = {(s,e,d) : m.addVar() for s in I for e in E for d in D} 
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
        if linear:
            self.M = {(s,e,d) : m.addVar(ub=1) for s in I for e in E for d in D}
        else:
            self.M = {(s,e,d) : m.addVar(vtype=GRB.BINARY) for s in I for e in E for d in D}
        
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
        S = self.S
        C = self.C
        D = self.D
        E = self.E
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
        self. vertical_clashes = {(s,e,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e for c in prefixes(d)) +
                        quicksum(X[t,(s[0]+1,s[1]),c] for t in T if t.get_edge_type_on_side(Side.TOP) == EdgeType.clash_type(e) 
                                    for c in prefixes(d)) <= 1) 
            for s in S if (s[0]+1,s[1]) in S for e in E for d in D}
            
        #constraints for if there are connections on any horizontal edges
        #Y variables only defined at the end, so they can be set if any of the X value prefixes are set
        #these are split up into two constraints to improve the LP relaxation
        #only define these rules for the full dice roll
        self.left_connections = {(s,e,d) :
            m.addConstr(Y[s, (s[0], s[1]+1), e, d] <= quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e for c in prefixes(d)))
            for s in S if (s[0],s[1]+1) in S for e in E for d in D}
            
        self.right_connections = {(s,e,d) :
            m.addConstr(Y[s, (s[0], s[1]+1), e, d] <= quicksum(X[t,(s[0],s[1]+1),c] for t in T if t.get_edge_type_on_side(Side.LEFT) == e for c in prefixes(d)))
            for s in S if (s[0],s[1]+1) in S for e in E for d in D}
            
        #constraints for if there are connections on any vertical edges
        #scenario definition as above   
        self.top_connections = {(s,e,d) :
            m.addConstr(Y[s, (s[0]+1, s[1]), e, d] <= quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e for c in prefixes(d)))
            for s in S if (s[0]+1,s[1]) in S for e in E for d in D}
        
        self.bottom_connections = {(s,e,d) :
            m.addConstr(Y[s, (s[0]+1, s[1]), e, d] <= quicksum(X[t,(s[0]+1,s[1]),c] for t in T if t.get_edge_type_on_side(Side.TOP) == e for c in prefixes(d)))
            for s in S if (s[0]+1,s[1]) in S for e in E for d in D}
        
            
        #there must be a connection to a piece played earlier or on this turn
        self.earlier_move_connection = {(t,s,c) :
            m.addConstr(X[t,s,c] <= (quicksum(X[tt,(s[0],s[1]-1),cc] for tt in T if tt.get_edge_type_on_side(Side.RIGHT) == t.get_edge_type_on_side(Side.LEFT) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.LEFT) != EdgeType.B and (s[0],s[1]-1) in S) else 0) +
                                     (quicksum(X[tt,(s[0],s[1]+1),cc] for tt in T if tt.get_edge_type_on_side(Side.LEFT) == t.get_edge_type_on_side(Side.RIGHT) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.RIGHT) != EdgeType.B and (s[0],s[1]+1) in S) else 0) + 
                                     (quicksum(X[tt,(s[0]-1,s[1]),cc] for tt in T if tt.get_edge_type_on_side(Side.BOTTOM) == t.get_edge_type_on_side(Side.TOP) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.TOP) != EdgeType.B and (s[0]-1,s[1]) in S) else 0) + 
                                     (quicksum(X[tt,(s[0]+1,s[1]),cc] for tt in T if tt.get_edge_type_on_side(Side.TOP) == t.get_edge_type_on_side(Side.BOTTOM) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.BOTTOM) != EdgeType.B and (s[0]+1,s[1]) in S) else 0))
            for t in T for s in S for c in C if c != tuple()}

    """
    constraints for joining exits
    """
    def _joining_exits_constraints(self):
        #unload the class variables into local variables for ease
        m = self.m
        T = self.T
        S = self.S
        D = self.D
        E = self.E
        I = self.I
        O = self.O
        X = self.X
        Y = self.Y
        F = self.F
        FF = self.FF
        G = self.G
        J = self.J
        
        #these are all done for only the complete dice rolls, so for d in D
        #the internal constraints also exist for every possible origin square o in O
        
        #the flow into an internal square must be the same as the flow out
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
            m.addConstr(quicksum(G[s,o,d] for s in O) == 1)
            for o in O for d in D}
            
        #add a bonus point if there is only one connection to the super sink (all exits connected)
        self.bonus_point = {d :
            m.addConstr((NUM_STARTS - 1)*J[d] <= quicksum(G[s,o,d] for s in O for o in O if s != o))
            for d in D}
            
            
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
        
        #these are only calculated for the full scenarios, for d in D
        
        #there must be two starting points and only 2 starting points
        self.two_ends = {(e,d) :
            m.addConstr(quicksum(K[s,e,d] for s in I) == 2)
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
            
        #there can only be flow on edges that have a connection of that type
        self.only_on_connected_edges = {(s,ss,e,d) :
            m.addConstr(L[s,ss,e,d] <= Y[s,ss,e,d])
            for s in I for ss in self._board.adjacents(s, internal=True, forward=True) for e in E for d in D}

        #this formulation allows for completely separate loops, handle removal in lazy constraints
        #except for basic size 4 loops, add all of those at the start because they are likely to get added   
        self.no_size_4_loops = {((r,c),e,d) :
            m.addConstr(L[(r,c),(r,c+1),e,d] + L[(r,c),(r+1,c),e,d] +
                        L[(r,c+1),(r+1,c+1),e,d] + L[(r+1,c),(r+1,c+1),e,d] <= 3)
            for r in range(NUM_ROWS-1) for c in range(NUM_COLS-1) for e in E for d in D}
            
        #don't set a start location and not have it scoring, this may be redundant with the two_ends equality
        self.end_bounds = {(s,e,d) :
            m.addConstr(K[s,e,d] <= M[s,e,d])
            for s in I for e in E for d in D}

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
        G = self.G
        J = self.J
        M = self.M
        
        #calculate the score for each full scenario, use a <= because the optimisation will force equality where important
        self.scoring = {d :
            m.addConstr(Alpha[d] <= quicksum(X[t,s,c] for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)) #centre square points
                                  + 4 * quicksum(G[s,o,d] for s in O for o in O if s != o)
                                  + J[d] #bonus point
                                  + quicksum(M[s,e,d] for s in I for e in E) #longest path points
                                  - quicksum(X[t,s,c] * t.loose_ends(s) for t in T for s in I for c in prefixes(d)) #subtraction for the number of loose ends (start of penalty calculation)
                                  + quicksum(Y[s,ss,e,dd] for (s,ss,e,dd) in Y if dd == d and s in I and ss in I) #these points are not lost if there is a join on that edge
            )
            for d in D}

    """
    set the objective function of the model, this depends on what the objective function was selected as
    """
    def _set_objective(self):
        #unpack into local variables to make naming cleaner
        m = self.m
        D = self.D
        Alpha = self.Alpha
        
        if self._objective == "expected-score":
            m.setObjective(quicksum(Alpha[d] * self._scenario_probability(d) for d in D), GRB.MAXIMIZE)
        
       
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
    def _set_gurobi_parameters(self, seed, folder):
        self.m.setParam('Seed',seed)
        self.m.setParam('MIPGap', 0)
        self.m.setParam('LazyConstraints', 1)
        self.m.setParam('LogFile', folder + "/log.txt")
        #self.m.setParam('BranchDir', 1)


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
    prints all scenarios listed in printD, if printD == "all", then prints all scenarios in D
    prints to folder, unless printPictures is True, when it will print all directly
    """
    def _print_scenarios(self, printD, printPictures, folder):
        if printD == "all": #if the argument was "all" then print all scenarios
            printD = self.D
            
        if printPictures == True: #print directly without saving
            for d in printD:
                self._print_scenario(d) 
        else: #save them all with different names in the given folder, this folder must exist
            for d in printD:
                self._print_scenario(d, file="{0}/solution {1}.png".format(folder, d))
                
    
    """
    print the board with the solution attached for a given scenario d
    """
    def _print_scenario(self, d, file=None):
        #find all the pieces and placements that we made and add them to the board
        added_squares = [] #track the squares that were added
        for s in self.S:
            for t in self.T:
                for c in prefixes(d):
                    if c != tuple() and self.X[t,s,c].x > 0.9:
                        self._board.add_tile(t, s, self._turn - 1 + len(c))
                        added_squares += [s]
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print(file)
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
        T = self.T
        D = self.D
        X = self.X
        Y = self.Y
        G = self.G
        M = self.M
        J = self.J
        Alpha = self.Alpha
        
        #print the results to a CSV
        resultsFile = folder + "/" + CSV_NAME
        with open(resultsFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Turn {0}".format(self._turn + i) for i in range(len(self._dice_rolls))] + 
                                 ["Score", "Connecting Exits", "Longest Railway", "Longest Highway", "Centre Points", "Errors", "Bonus Point"])
            for d in D:
                score = round(Alpha[d].x)
                centre_points = round(sum(X[t,s,c].x for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)))
                connecting_exits = round(4 * sum(G[s,o,d].x for s in O for o in O if s != o))
                longest_railway = round(sum(M[s,EdgeType.R,d].x for s in I))
                longest_highway = round(sum(M[s,EdgeType.H,d].x for s in I))
                errors = round(-1* sum(X[t,s,c].x * t.loose_ends(s) for t in T for s in I for c in prefixes(d))
                              + sum(Y[s,ss,e,dd].x for (s,ss,e,dd) in Y if dd == d and s in I and ss in I))
                bonus_point = round(J[d].x)
                csv_writer.writerow([turn for turn in d] + [score, connecting_exits, longest_railway, 
                                                            longest_highway, centre_points, errors, bonus_point])
        
        
    #############################CALLBACK FUNCTIONS############################
        
    """
    The callback used in the Railroad Ink solver
    """    
    def _callback(self, model, where):
        if where == GRB.Callback.MIPSOL:
            #get the X and L values in the solution
            XV = {k : v for (k,v) in zip(self.X.keys(), model.cbGetSolution(list(self.X.values())))}
            LV = {k : v for (k,v) in zip(self.L.keys(), model.cbGetSolution(list(self.L.values())))}
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
                                    m.cbLazy(len(squares) - 2 >= quicksum(L[squares[i],squares[i+1],e,d] for i in range(len(squares)-1)))
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
    Do the checks for adding lazy constraints,
    this is a recursive function, if the checks for one step of the scenario pass, then it is called for all children of
    that scenario
    """        
    def _lazy_checks(self, scenario, XV, LV):
        #unpack some needed variables
        m = self.m
        I = self.I
        S = self.S
        T = self.T
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
        isolatedSquareConstraintsAdded = False
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
            isolatedSquareConstraintsAdded = True
            
        
        
        #if there were no isolated pieces, then all pieces were added to the board in the earlier process
        missingPieces = self._find_missing_pieces(playedTiles, pieceCounts)
        
        canPlaceMissingPiece = self._can_place_a_missing_piece(missingPieces)
        if canPlaceMissingPiece:
            m.cbLazy(1 <= quicksum(1 - X[t,s,scenario] for (t,s) in playedTiles) #we can move an already played tile
                            + quicksum(X[t,s,scenario] for piece in missingPieces for t in Tile.get_variations(piece) for s in I) #play a missing piece
                            + (quicksum(X[t,s,scenario] for piece in SPECIAL_PIECES for t in Tile.get_variations(piece) for s in I) 
                                    if not self._board.all_specials_used() else 0)) #play a special piece
            
        #finally we also want to check for any loops for longest paths
        self._add_any_loop_lazy_constraints(scenario, LV)
    
         
        #if we haven't added any lazy constraints for this scenario, do the checks for all the child scenarios
        if not canPlaceMissingPiece and not isolatedSquareConstraintsAdded and len(scenario) < len(self._dice_rolls):
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
#    s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
#    s.solve(folder="rulebook", printOutput=True, printPictures=True, printD="all")
    
#    board = Board()
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,0), 3)
#    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 3)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,2), 4)
#    board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R180), (1,3), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (2,1), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (2,3), 5)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,0), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,1), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (3,2), 3)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,6), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (4,2), 3)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R180, flip=False), (4,3), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_JUNCTION, Rotation.I), (4,4), 5)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,0), 1)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (5,1), 1)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.I, flip=True), (5,2), 2)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (5,3), 4)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,6), 5)
#    board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (6,1), 1)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (6,3), 1)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (6,4), 5)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270, flip=False), (6,5), 5)
#    
#    dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
#                             Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
#                  [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
#                             Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 0.6),
#                   DiceRoll({Piece.HIGHWAY_T : 1, Piece.RAILWAY_T : 1,
#                             Piece.HIGHWAY_CORNER : 1, Piece.STRAIGHT_STATION : 1}, 0.4)]]
#                   #DiceRoll({Piece.RAILWAY_CORNER : 2, 
#                   #          Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 0.3)]
#                       
#   
#    s = RailroadInkSolver(board, 6, dice_rolls, "expected-score")
#    s.solve(folder="six-three", printOutput=True, printPictures=False, printD="all")
#    
  
    
    board = Board()
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,0), 3)
    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 3)
    #board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,2), 4)
    #board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R180), (1,3), 4)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (2,1), 2)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,0), 2)
    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,1), 2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (3,2), 3)
    #board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,6), 4)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (4,2), 3)
    #board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R180, flip=False), (4,3), 4)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,0), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (5,1), 1)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.I, flip=True), (5,2), 2)
    #board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (5,3), 4)
    board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (6,1), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (6,3), 1)
    
    dice_rolls = [[DiceRoll({Piece.RAILWAY_STRAIGHT : 2, Piece.HIGHWAY_STRAIGHT : 1,
                             Piece.CORNER_STATION : 1}, 1)],
                  [DiceRoll({Piece.RAILWAY_STRAIGHT : 2, Piece.HIGHWAY_CORNER : 1,
                             Piece.CORNER_STATION : 1}, 1)],
                  [DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
                             Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
                  [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
                             Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 1)]]    

    s = RailroadInkSolver(board, 4, dice_rolls, "expected-score")
    s.solve(folder="one-one-one-one", printOutput=True, printPictures=False, printD="all")