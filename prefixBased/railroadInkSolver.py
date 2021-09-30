
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

#adjust the results folder based on where this is being called
#hardcode this to ensure that whenever files are copied to and from the cluster
#that it always saves to the right place
if "uqlkamol" in os.getcwd():
    RESULTS_FOLDER = "/data/uqlkamol/railroad-ink-results"
else:
    RESULTS_FOLDER = "results"
    
RESULTS_CSV = "points.csv"
DECISIONS_CSV = "decisions.csv"
SETTINGS_CSV = "settings.csv"
INFO_CSV = "info.csv"
ALTERNATIVES_CSV = "alternatives.csv"

#default values for some of the tuneable characteristics
DEFAULT_OPEN_ENDS_POINTS = [2.5, 2.5, 2, 1.6, 1.4, 0.5, 0]
DEFAULT_FAKE_CONNECTIONS_POINTS = [0.6,0.6,0.8,1,1.5,2.5,4]
DEFAULT_FAKE_CONNECTIONS_MAX = [6,10,18,16,12,6,0]
DEFAULT_INTERNAL_SINK_SCORES = [3,3,2.5,2,1.5,1,0]

#sets of variables to make binary
#the variables that must be binary for the model to be correct
MINIMAL_BINARY_SET = {'X', 'J'}
#the default choices
DEFAULT_BINARY_SET = {'X', 'Y', 'V', 'W', 'Z', 'J', 'G', 'Q', 'K', 'M', 'B', 'VV', 'YY'}
#all possible binaries values
MAXIMAL_BINARY_SET = {'X', 'Y', 'V', 'W', 'Z', 'F', 'FF', 'J', 'G', 'Q', 'K', 'L', 'M', 'B', 'VV', 'YY'}

DEFAULT_GUROBI_PARAMS = {'Heuristics': 0.001,
                         'Cuts': 1,
                         'GomoryPasses': 0}

DEFAULT_PRIORITIES = {"Y": 10}

DEFAULT_TIMEOUTS = [-1, -1, -1, -1, -1, -1, -1] #measured in seconds (-1 for no timeout)

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
    col_gen - whether to generate all possible moves in advance with a priori column generation and use these
    intermediate_connections - whether to introduce variables for intermediate connections
    piece_cap - the maximum number of each piece that can be played as a generic piece
    isolated_pieces - how to handle isolated pieces, options are "lazy" for using lazy constraints or "relief"
            for using a flow problem
    path_loops - how to handle path loops, options are "lazy" for using lazy constraints or "relief" for using
            a flow problem
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
    old_constraints - if True, uses older versions of constraints that are not as tight
    binary_set - set of variables to make binary
    gurobi_params - dictionary of gurobi parameters to set
    timeouts - array of timeouts measured in seconds, -1 at each index if there shouldn't be a timeout
    linear - if True then solves the linear relaxation, else solves the MILP
    linear_tree - if True then treats the scenario tree as a linear problem and only the first move as integer
    solution_count - determines how many solutions to produce. If 1 then does a general solve, if >1 then
            creates a list of that many best solutions found. Requires only 1 scenario on the next turn
    """
    def __init__(self, board, turn, dice_rolls, objective, specials=True,
                 col_gen=False, intermediate_connections=False, piece_cap=-1,
                 isolated_pieces="lazy", path_loops="relief",
                 connecting_exits=True, longest_paths=True, errors=True,
                 open_ends=False, open_end_points=DEFAULT_OPEN_ENDS_POINTS,
                 fake_connections=False, fake_connections_cost=DEFAULT_FAKE_CONNECTIONS_POINTS, fake_connections_max=DEFAULT_FAKE_CONNECTIONS_MAX,
                 internal_sinks=False, internal_sink_scores=DEFAULT_INTERNAL_SINK_SCORES,
                 old_constraints=False,
                 binary_set=DEFAULT_BINARY_SET,
                 gurobi_params=DEFAULT_GUROBI_PARAMS,
                 branch_priorities=DEFAULT_PRIORITIES,
                 timeouts=DEFAULT_TIMEOUTS,
                 linear=False, linear_tree=False, solution_count=1):
        self._board = board
        self._turn = turn
        self._dice_rolls = dice_rolls
        self._objective = objective
        self._specials = specials
        self._col_gen = col_gen
        self._intermediate_connections = intermediate_connections
        self._piece_cap = piece_cap
        self._isolated_pieces = isolated_pieces
        self._path_loops = path_loops
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
        self._old_constraints = old_constraints
        self._binary_set = binary_set
        self._gurobi_params = gurobi_params
        self._branch_priorities = branch_priorities
        self._timeouts = timeouts
        self._linear = linear
        self._linear_tree = linear_tree
        self._solution_count = solution_count
        #check for if there is even a special to be played, don't add them to the model if there isn't
        if self._board.all_specials_used():
            self._specials = False
        #calculate the turn index for the final move for indexing into scoring arrays
        self._end_turn_index = self._turn - 2 + len(dice_rolls)
    
    """
    generates all possible scenarios using the dice rolls. Does this recursively so must be passed lists to build
    current_list - the current scenario 
    D - list of all final scenarios
    C - list of every step in every scenario
    to generate all possible scenarios, call with self._generate_scenarios([], D, C) with D, C initialise as []
    """
    def _generate_scenarios(self, current_list, D, C):
        if len(current_list) == len(self._dice_rolls):
            D += [tuple(current_list)]
        else:
            next_index = len(current_list)
            for next_val in range(len(self._dice_rolls[next_index])):
                current_list += [next_val]
                self._generate_scenarios(current_list, D, C)
        C += [tuple(current_list)]
        if len(current_list) > 0:
            current_list.pop()    
    
    """
    create and solve an IP that gives the solutions to the railroad ink problem
    folder - a folder to print all information to, this will include the log, the results csv and any pictures, None if no results should be saved
    print_output - whether to print Gurobi output to stdout
    printD - a list of scenarios to print pictures for, or "all" if all scenarios should be printed, default is to not print
    seed - the seed to use for gurobi
    tune - if non-zero, will perform a tune with the given length of time instead of a normal search
    lazy_constraints - whether or not to include lazy constraints
    """
    def solve(self, folder="last-run", print_output=False, printD=[], seed=0, tune=0,
              lazy_constraints=True):

        self._start_time = time.time()
        
        if folder != None:
            folder = "{0}/{1}".format(RESULTS_FOLDER, folder) #update the folder name  
            #create an empty folder to store all the results in
            create_empty_folder(folder)
            
        #init the multi solution framework if needed
        if self._solution_count > 1:
            self._init_multi_solution()
        
        #create the model
        self.m = Model("Railroad Ink")
        
        self._create_sets()
        
        self._create_variables()
        
        self._set_branch_priorities()
        
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
        with contextlib.redirect_stdout(self._print_stream_location(print_output)):
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
         
        self._end_time = time.time()
            
        if tune == 0:
            self._create_output(folder, printD)
            
        
        #don't have any return values, instead we can get the results from the class
        
    """
    get the result of the optimisation
    """
    def get_result(self):
        if self._solution_count == 1:
            try:
                return self.m.objval
            except AttributeError:
                return -1 #had an error here once, return -1 to flag where it was
        else:
            return 0 #the objective value isn't determined when multiple solutions are returned
        
    """
    returns a list of solutions if solution_count was set > 0
    returns a list of (tile, square) lists
    """
    def get_multiple_solutions(self):
        solns = []
        for soln_id in self._solutions:
            solns.append(self._solution_moves[soln_id])
        return solns
    
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
                            moves.append((t,s))
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
        
        #if we are using column generation, then generate all the possible moves
        if self._col_gen:
            self.A = self._board.all_possible_moves(self._dice_rolls[0][0].get_dice(), self._specials)


    """
    determine whether or not a given variable should be binary or continuous given the binary set
    """
    def _binary(self, var, scenario=None):
        #override these if using old constraints
        if self._old_constraints and var in {"L", "K", "M"} and not self._linear:
            return GRB.BINARY
        #override these if doing the linear_tree version
        if self._linear_tree:
            #the only binary constraints in the problem are the first turn movements
            return GRB.BINARY if var == "X" and scenario == (0,) else GRB.CONTINUOUS
        #return binary if in the given binary set
        return GRB.BINARY if var in self._binary_set and not self._linear else GRB.CONTINUOUS

    """
    create all the variables used in the Railroad Ink problem
    """
    def _create_variables(self):
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
        self.X = {(t,s,c) : m.addVar(vtype=self._binary('X', c), ub=1) for t in T for s in S for c in C}
            
        #y variables for whether there is a link between adjacent squares with edge type e with dice rolls d
        #these variables are only calculated at the end of the scenarios, not during
        #for ease, create entries in the opposite direction that point to the same variables            
        self.Y = {}
        for s in S:
            for e in E:
                for d in D:
                    for ss in self._board.adjacents(s, forward = True):
                        self.Y[s,ss,e,d] = m.addVar(vtype=self._binary('Y'), ub=1)
                        #use the same variable in both directions
                        self.Y[ss,s,e,d] = self.Y[s,ss,e,d]

        #V is for whether there is a connection on each side  
        self.V = {(s,ss,e,d) : m.addVar(vtype=self._binary('V'), ub=1) 
                for s in S for ss in self._board.adjacents(s) for e in E for d in D}
        
        if self._intermediate_connections:
            #y' and v' variables are connection variables for the first placement
            self.YY = {}
            for s in S:
                for e in E:
                    for ss in self._board.adjacents(s, forward=True):
                        self.YY[s,ss,e] = m.addVar(vtype=self._binary('YY'), ub=1)
                        self.YY[ss,s,e] = self.YY[s,ss,e]
            self.VV = {(s,ss,e) : m.addVar(vtype=self._binary('VV'), ub=1)
                    for s in S for ss in self._board.adjacents(s) for e in E}
        
        #b variables are for whether any of the generated columns are set
        if self._col_gen:
            self.B = {a : m.addVar(vtype=self._binary('B'), ub=1)
                    for a in self.A}

        #w variables are for any fake connections made
        if self._fake_connections:
            self.W = {(s,ss,e,d) : m.addVar(vtype=self._binary('W'), ub=1) 
                    for s in S for ss in self._board.adjacents(s) for e in E for d in D}
            
        #z variables for how many open ends there are attached to any placed piece
        #only if we are adding points for open ends
        if self._open_ends:
            self.Z = {(s,ss,d) : m.addVar(vtype=self._binary('Z'), ub=1) 
                    for s in I for ss in self._board.adjacents(s, internal=True) for d in D}
            
        #r variables for the isolated placement removal flow problem
        if self._isolated_pieces == "relief":
            self.R = {(s,ss,c) : m.addVar(ub=5) 
                    for s in S for ss in self._board.adjacents(s) for c in C if c != tuple()}
        
        #CONNECTING START POINTS VARIABLES
        if self._connecting_exits:
            if not self._old_constraints:
                #each of these is defined for every single possible set of dice rolls d in D
                #the flow problem is also defined for every start square 'o'
                #these are all linear variables since we start with only 1 as an input
                #the flow of joins between two adjacent squares
                self.F = {(s,ss,o,e,d): m.addVar(vtype=self._binary('F'), ub=1) 
                        for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D}
                #transfer flow between rails and highways at square s (from e)
                self.FF = {(s,o,e,d) : m.addVar(vtype=self._binary('FF'), ub=1) 
                        for s in I for o in O for e in E for d in D} 
                
                #whether the extra point for connecting all of them is earned
                self.J = {d : m.addVar(vtype=self._binary('J'), ub=1) for d in D}
                #flow from a start square to the super sink
                self.G = {(s,o,d) : m.addVar(vtype=self._binary('G'), ub=1) for s in O for o in O for d in D}   
                    
                #Q variables are for the internal super sink connections, so any connection to the super sink can be via an internal edge
                #if that is an open end
                if self._internal_sinks:
                    self.Q = {(s,ss,o,e,d) : m.addVar(vtype=self._binary('Q'), ub=1) 
                            for s in S for ss in self._board.adjacents(s) for o in O for e in E for d in D}
            else:
                #these variables are not included in the final model, only if an old version is being used
                self.F = {(s,ss,e,d) : m.addVar(ub=12)
                        for s in S for ss in self._board.adjacents(s) for e in E for d in D}
                self.FF = {(s,e,d) : m.addVar(ub=12) 
                        for s in I for e in E for d in D} 
                self.G = {(s,d) : m.addVar(ub=12) for s in O for d in D}   
                self.H = {(s,d) : m.addVar(vtype=(GRB.CONTINUOUS if self._linear else GRB.BINARY)) for s in O for d in D} 
                self.J = {d : m.addVar(vtype=self._binary('J'), ub=1) for d in D}
        
        #LONGEST RAILWAY/HIGHWAY VARIABLES
        if self._longest_paths:
            #each of these is defined for every single possible set of dice rolls d in D
            #whether square s is an end square of the path
            self.K = {(s,e,d) : m.addVar(vtype=self._binary('K'), ub=1) 
                    for s in I for e in E for d in D}
                
            #whether there is a longest path connection between squares s and ss
            #define this similarly to the Y variables in that two references to the same variable exist
            self.L = {}
            for s in I:
                for e in E:
                    for d in D:
                        for ss in self._board.adjacents(s, forward = True, internal=True):
                            self.L[s,ss,e,d] = m.addVar(vtype=self._binary('L'), ub=1)
                            self.L[ss,s,e,d] = self.L[s,ss,e,d]
            
            #whether square s counts towards the "e" longest road
            self.M = {(s,e,d) : m.addVar(vtype=self._binary('M'), ub=1) 
                    for s in I for e in E for d in D}
            
            #relief flow problem, flow variables for ensuring that there is some flow to a start
            #these are always linear because they are not restricted to the 0-1 domain
            self.N = {(s,ss,e,d) : m.addVar()
                    for s in I for ss in self._board.adjacents(s, internal=True) for e in E for d in D}
            
        #SCORING VARIABLES
        #the score for every final scenario
        self.Alpha = {d : m.addVar() for d in D}   
        #the objective value
        self.Beta = m.addVar()
            
    """
    adjust the branch priorities according to the branch priority dictionary
    """
    def _set_branch_priorities(self):
        #if there is a better way of doing this than writing them all out like this, I don't see it
        #I could probably add all of these to a dictionary
        for varname in self._branch_priorities:
            vardict = getattr(self, varname) #get the value from the class dictionary
            priority = self._branch_priorities[varname]
            #then for all variables by this name, set the branch priorities
            for a in vardict:
                vardict[a].BranchPriority = priority

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
            
        #add constraints for the use of pieces, this is split up to allow for generic pieces
        self.use_pieces = {}
        for c in C:
            if c != tuple():
                dice = self._dice_rolls[len(c) - 1][c[-1]].get_dice()
                for p in dice:
                    #add upper bounds on any pieces that are allowed
                    self.use_pieces[p,c] = m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) <= dice[p])
                for p in BASIC_PIECES:
                    if p not in dice and Piece.BASIC not in dice:
                        self.use_pieces[p,c] = m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) <= 0)
                for p in JUNCTION_PIECES:
                    if p not in dice and Piece.JUNCTION not in dice:
                        self.use_pieces[p,c] = m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) <= 0)   
                for p in START_PIECES:
                    self.use_pieces[p,c] = m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) <= 0)   

#old more readable version of this constraint (doesn't account for generic pieces)
#        self.use_pieces = {(p,c) : 
#            m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
#                                 for t in Tile.get_variations(p)) <= 
#                        (self._dice_rolls[len(c) - 1][c[-1]].get_dice().get(p, 0))) 
#                        #^ this gets the dictionary of this dice roll, then searches for the piece, defaulting to zero
#            for p in BASIC_PIECES + JUNCTION_PIECES + START_PIECES for c in C if c != tuple()}
             
        #bound the number of generic pieces of each type that can be played
        if self._piece_cap > 0:
            self.generic_piece_caps = {p :
                m.addConstr(quicksum(X[t,s,c] for c in C if (c != tuple() and (self._dice_rolls[len(c) - 1][c[-1]].get_dice().get(Piece.BASIC,None) != None)) 
                                              for t in Tile.get_variations(p) for s in S if self._board.is_square_free(s)) <= self._piece_cap)
                for p in BASIC_PIECES + JUNCTION_PIECES}
        
        #if we are using column generation, add those constraints
        if self._col_gen:
            A = self.A
            B = self.B
            #can only pick one column to use overall
            self.pick_one_col = m.addConstr(quicksum(B[a] for a in A) == 1)
            
            #can only set a piece as played if a column containing it is played
            #this is only done for the first move
            #do a little preprocessing to reduce the execution time by finding all plays in A that have the same (s,t) pair
            plays = {}
            for t in T:
                for s in S:
                    plays[t,s] = []
            for a in A:
                #go through all the plays in this move
                for (s,t) in a:
                    plays[t,s].append(a)
            self.only_play_if_col_played = {(t,s) :
                m.addConstr(X[t,s,(0,)] == quicksum(B[a] for a in plays[t,s]))
                for (t,s) in plays}
            
    
        if self._specials:
            #play special pieces at most once each in every possible dice roll scenario
            self.special_once = {(p,d):
                    m.addConstr(quicksum(X[t,s,c] for s in S
                            for t in Tile.get_variations(p) for c in prefixes(d)) <= 1)
                    for p in SPECIAL_PIECES for d in D}
                
            #play at most one special piece per turn (in every scenario)
            #only allow these to be played if there is a special allowed for this dice roll
            self.one_special_per_turn = {c :
                m.addConstr(quicksum(X[t,s,c] for s in S for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=
                            self._dice_rolls[len(c) - 1][c[-1]].specials())
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
                for s in S for ss in self._board.adjacents(s) for e in E for d in D}
        else: 
            #this is the regular constraint
            if self._old_constraints:
                #this is not a good constraint, and has been superseded by the below constraint
                #but is here to run tests that show the improvement
                self.old_connections = {(s,ss,e,d) :
                    m.addConstr(2*Y[s,ss,e,d] <= V[s,ss,e,d] + V[ss,s,e,d])
                    for s in S for ss in self._board.adjacents(s, forward=True) for e in E for d in D}
            else:
                #can have a connection on an edge only if there is actually a connection there
                self.connections = {(s,ss,e,d) :
                    m.addConstr(Y[s,ss,e,d] <= V[s,ss,e,d])
                    for s in S for ss in self._board.adjacents(s) for e in E for d in D}
                    
        #add some extra constraints for the intermediate connections if we are using them
        if self._intermediate_connections:
            VV = self.VV
            YY = self.YY
            
            #determine the v' values, the same constraint just for d = (0,)
            self.vv_values = {(s,ss,e) :
                m.addConstr(VV[s,ss,e] == quicksum(X[t,s,c] for c in prefixes((0,)) for t in T if t.get_edge_type_on_side(side) == e))
            for s in S for ss,side in self._board.adjacents_with_sides(s) for e in E}
                
            #determine the y' values given the v' values
            self.yy_connections = {(s,ss,e) :
                m.addConstr(YY[s,ss,e] <= VV[s,ss,e])
                for s in S for ss in self._board.adjacents(s) for e in E}
                
            #bound all of the y values using the y' values
            self.yy_bounds = {(s,ss,e,d) :
                m.addConstr(Y[s,ss,e,d] >= YY[s,ss,e])
                for s in S for ss in self._board.adjacents(s) for e in E for d in D}
            
            
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
                for s in I for ss,side in self._board.adjacents_with_sides(s) for c in C if c != tuple()}
            #we can have a relief connection to any piece played with a connection on that edge on this turn or earlier
            self.relief_connections_2 = {(s,ss,c):
                m.addConstr(R[s,ss,c] <= 5*quicksum(X[t,ss,cc] for cc in prefixes(c) 
                                         for t in T if t.get_edge_type_on_side(Side.opposite(side)) != EdgeType.B))
                for s in I for ss,side in self._board.adjacents_with_sides(s) for c in C if c != tuple()}
                
            self.relief_flow = {(s,c):
                m.addConstr(quicksum(X[t,s,c] for t in T) + quicksum(R[ss,s,c] for ss in self._board.adjacents(s)) <=
                            quicksum(R[s,ss,c] for ss in self._board.adjacents(s)) + 5*quicksum(X[t,s,cc] for t in T for cc in prefixes(c) if c != cc))
                for s in I for c in C if c != tuple()}
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
            self.open_end_scoring_1 = {(s,ss,d):
                m.addConstr(Z[s,ss,d] <=  quicksum(V[s,ss,e,d] for e in E))
                for s in I for ss in self._board.adjacents(s, internal=True) for d in D}           
              
            #not an open end if there is anything on the other side
            self.open_end_scoring_2 = {(s,ss,d): 
                m.addConstr(Z[s,ss,d] <= 1 - quicksum(X[t,ss,c] for t in T for c in prefixes(d)))
                for s in I for ss in self._board.adjacents(s,internal=True) for d in D}
                
        #if it is turn 1, reduce symmetry by forcing the top left to have more pieces
        if self._turn == 1:
            self._symmetry_removal = {
                    m.addConstr(quicksum(X[t,(row,col),c] for row in range(3) for col in range(3) for t in T ) >=
                                quicksum(X[t,(row,col),c] for row in range(rS, rS+3) for col in range(cS, cS+3) for t in T ))
                    for (rS, cS) in [(0,4),(4,0),(4,4)] for c in C if len(c) == 1}

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
        V = self.V
        X = self.X
        Y = self.Y
        F = self.F
        FF = self.FF
        G = self.G
        J = self.J
        
        #these are all done for only the complete dice rolls, so for d in D
        #the internal constraints also exist for every possible origin square o in O
        if not self._old_constraints:
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
        else:
            #these are old constraints, not part of the final model
            H = self.H
            self._old_connecting_1 = {(s,e,d) :
                m.addConstr(quicksum(F[s,ss,e,d] for ss in self._board.adjacents(s)) + FF[s,e,d] ==
                                quicksum(F[ss,s,e,d] for ss in self._board.adjacents(s)) + FF[s,EdgeType.clash_type(e),d])
                for s in I for e in E for d in D}
            self._old_connecting_2 = {(s,d) :
                m.addConstr(1 + quicksum(F[ss,s,e,d] for ss in self._board.adjacents(s) for e in E) ==
                            quicksum(F[s,ss,e,d] for ss in self._board.adjacents(s) for e in E) + G[s,d])
                for s in O for d in D}
            self.old_connecting_3 = { (s,d) :
                m.addConstr(G[s,d] <= 12 * H[s,d])
                for s in O for d in D}
            self.old_connecting_4 = {(s,ss,e,d) :
                m.addConstr(F[s,ss,e,d] <= 12 * Y[s,ss,e,d])    
                for s in S for ss in self._board.adjacents(s) for e in E for d in D}
            self.old_connecting_5 = {(s,e,d):
                m.addConstr(FF[s,e,d] <= 12 * quicksum(X[t,s,c] for t in T if t.get_piece() in SWITCH_PIECES for c in prefixes(d)))
                for s in I for e in E for d in D}
            self.old_connecting_6 = {d:
                m.addConstr(11 * J[d] <= quicksum(1 - H[s,d] for s in O))
                for d in D}

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
            
        #there can only be flow on edges that have a connection of that type
        self.only_on_connected_edges = {(s,ss,e,d) :
            m.addConstr(L[s,ss,e,d] <= Y[s,ss,e,d])
            for s in I for ss in self._board.adjacents(s, internal=True, forward=True) for e in E for d in D}
            
        #add all of the LP tightening constraints (unless doing the old version trial)
        if not self._old_constraints:
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
    
            #don't set a start location and not have it scoring, this may be redundant with the two_ends equality
            self.end_bounds = {(s,e,d) :
                m.addConstr(K[s,e,d] <= M[s,e,d])
                for s in I for e in E for d in D}
            
        if self._path_loops == "relief":
            #relief constraints
            self.path_relief = {(s,e,d) :
                m.addConstr(quicksum(N[s,ss,e,d] for ss in self._board.adjacents(s, internal=True)) + 16 * K[s,e,d] >=
                            quicksum(N[ss,s,e,d] for ss in self._board.adjacents(s, internal=True)) + M[s,e,d])
                for s in I for e in E for d in D}
                
            self.path_relief_on_edges = {(s,ss,e,d) :
                m.addConstr(N[s,ss,e,d] <= 16 * L[s,ss,e,d])
                for s in I for ss in self._board.adjacents(s, internal=True) for e in E for d in D}
        elif self._path_loops == "lazy":
            #remove all size 4 loops by default, larger loops handled in lazy constraints
            self.size_4_loops = {((r,c),e,d) :
                m.addConstr((3/4)*(M[(r,c),e,d] + M[(r,c+1),e,d] + M[(r+1,c),e,d] + M[(r+1,c+1),e,d]) >=
                            L[(r,c),(r,c+1),e,d] + L[(r,c),(r+1,c),e,d] +
                            L[(r,c+1),(r+1,c+1),e,d] + L[(r+1,c),(r+1,c+1),e,d])
                for r in range(NUM_ROWS-1) for c in range(NUM_COLS-1) for e in E for d in D}          
            

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
        if not self._old_constraints:
            self.scoring = {d :
                m.addConstr(Alpha[d] == quicksum(X[t,s,c] for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)) #centre square points
                                      + (4 * quicksum(G[s,o,d] for s in O for o in O if s != o) + J[d] if self._connecting_exits else 0) #connecting exits points
                                      + (quicksum(M[s,e,d] for s in I for e in E) if self._longest_paths else 0) #longest path points
                                      - (quicksum(X[t,s,c] * t.loose_ends(s) for t in T for s in I for c in prefixes(d)) #subtraction for the number of loose ends (start of penalty calculation)
                                      - quicksum(Y[s,ss,e,dd] for (s,ss,e,dd) in Y if dd == d and s in I and ss in I) #these points are not lost if there is a join on that edge
                                              if self._errors else 0)
                )
                for d in D}
        else:
            H = self.H
            self.old_scoring = {d :
                m.addConstr(Alpha[d] == quicksum(X[t,s,c] for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)) #centre square points
                                      + (48 - 4 * quicksum(H[s,d] for s in O) + J[d]) #connecting exits points
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
        Beta = self.Beta
        
        if self._objective == "expected-score":
            #m.setObjective(quicksum(Alpha[d] * self._scenario_probability(d) for d in D), GRB.MAXIMIZE)
            #scores regularly but adds terms for if objective modifications were made3
            m.addConstr(Beta == quicksum((Alpha[d] 
                                    + (quicksum(self.Z[s,ss,d] for s in I for ss in self._board.adjacents(s, internal=True)) * self._open_end_points[self._end_turn_index] 
                                             if self._open_ends else 0)
                                    + (quicksum(self.Q[s,ss,o,e,d] for s in S for ss in self._board.adjacents(s) for o in O for e in E) * self._internal_sink_scores[self._end_turn_index]
                                            if self._internal_sinks else 0)
                                    - (quicksum(self.W[s,ss,e,d] for s in S for ss in self._board.adjacents(s) for e in E) * self._fake_connections_cost[self._end_turn_index]
                                             if self._fake_connections else 0)) 
                                    * self._scenario_probability(d) for d in D))
            m.setObjective(Beta, GRB.MAXIMIZE)
       
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
            for param in self._gurobi_params:
                self.m.setParam(param, self._gurobi_params[param])
        else:
            self.m.setParam('TuneTimeLimit', tune)
        #set up the timeout if it is needed
        if self._timeouts[self._turn - 1] != -1:
            self.m.setParam('TimeLimit', self._timeouts[self._turn - 1])
        if folder != None:
            self.m.setParam('LogFile', folder + "/log.txt")

    #############################OUTPUT######################################
    
    """
    creates all output files
    """
    def _create_output(self, folder, printD):
        if folder != None:
            if self._solution_count == 1:
                #create images for any scenarios
                self._print_scenarios(printD, folder)
                #create the csv for points
                self._make_points_csv(folder)
                #create the csv for the moves being made
                self._make_scenarios_csv(folder)
            else:
                self._make_alternatives_csv(folder)
            #create the csv for the settings
            self._make_settings_csv(folder)
            #create the csv with information about the run
            self._make_info_csv(folder)
        
    
    """
    determine where to print stdout to depending on whether or not we want to see it
    if print_output is True, returns stdout, if False returns a fake printer that does nothing
    """
    def _print_stream_location(self, print_output):
        #set up where to print to
        if print_output == True:
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
    def _make_points_csv(self, folder):
        #unpack some variables
        I = self.I
        O = self.O
        S = self.S
        T = self.T
        D = self.D
        E = self.E
        X = self.X
        Y = self.Y
        
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
                if self._old_constraints:
                    H = self.H
                    connecting_points = round(48 - 4 * sum(H[s,d].x for s in O) + J[d].x)
                else:
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
                
    """
    make a csv containing the moves made in all scenarios
    """
    def _make_scenarios_csv(self, folder):
        S = self.S
        T = self.T
        X = self.X
        C = self.C
        
        movesFile = folder + "/" + DECISIONS_CSV
        with open(movesFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            for c in C:
                csv_writer.writerow(["Scenario {0}".format(c)])
                for s in S:
                    for t in T:
                        if X[t,s,c].x > 0.9:
                            csv_writer.writerow([t.get_piece(), t.get_rotation(), t.get_flip(), s[0], s[1]])        
                            
                            
    """
    make a file containing all the settings used for this run
    """
    def _make_settings_csv(self, folder):
        settingsFile = folder + "/" + SETTINGS_CSV
        with open(settingsFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["turn", self._turn])
            csv_writer.writerow(["objective", self._objective])
            csv_writer.writerow(["specials", self._specials])
            csv_writer.writerow(["col_gen", self._col_gen])
            csv_writer.writerow(["intermediate_connections", self._intermediate_connections])
            csv_writer.writerow(["isolated_pieces", self._isolated_pieces])
            csv_writer.writerow(["path_loops", self._path_loops])
            csv_writer.writerow(["connecting_exits", self._connecting_exits])
            csv_writer.writerow(["longest_paths", self._longest_paths])
            csv_writer.writerow(["errors", self._errors])
            csv_writer.writerow(["open_ends", self._open_ends])
            csv_writer.writerow(["fake_connections", self._fake_connections])
            csv_writer.writerow(["internal_sinks", self._internal_sinks])
            csv_writer.writerow(["open_end_points"] + self._open_end_points)
            csv_writer.writerow(["fake_connections_cost"] + self._fake_connections_cost)
            csv_writer.writerow(["fake_connections_max"] + self._fake_connections_max)
            csv_writer.writerow(["internal_sink_scores"] + self._internal_sink_scores)
            csv_writer.writerow(["old_constraints", self._old_constraints])
            csv_writer.writerow(["linear", self._linear])
            csv_writer.writerow(["linear_tree", self._linear_tree])
            csv_writer.writerow(["solution_count", self._solution_count])
            csv_writer.writerow(["binary_set"] + list(self._binary_set))
            csv_writer.writerow(["timeouts"] + self._timeouts)
            csv_writer.writerow(["Gurobi Params"])
            for param in self._gurobi_params:
                csv_writer.writerow([param, self._gurobi_params[param]])
            csv_writer.writerow(["Priorities"])
            for var in self._branch_priorities:
                csv_writer.writerow([var, self._branch_priorities[var]])
                
    """
    make a csv containing all the information about this run, such as the time taken, lazy constraints
    added, etc
    """
    def _make_info_csv(self, folder):
        infoFile = folder + "/" + INFO_CSV
        with open(infoFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["gurobi time", self.get_gurobi_runtime()])
            csv_writer.writerow(["total time", self.get_total_runtime()])
            csv_writer.writerow(["result", self.get_result()])
            csv_writer.writerow(["status", GRB.OPTIMAL])
            if self._col_gen:
                csv_writer.writerow(["columns", len(self.A)])
                
    """
    create a csv containing information about all the different solutions
    """        
    def _make_alternatives_csv(self, folder):
        alternatives_file = f"{folder}/{ALTERNATIVES_CSV}"
        with open(alternatives_file, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Move", "Piece", "Rotation", "Flip", "Row", "Col"])
            for i, soln in enumerate(self.get_multiple_solutions()):
                for move in soln:
                    csv_writer.writerow([i, move[0].get_piece(), move[0].get_rotation(), move[0].get_flip(),
                                     move[1][0], move[1][1]]) 
        
    #############################CALLBACK FUNCTIONS############################
      
    """
    initialise some variables used for tracking multiple solutions
    """
    def _init_multi_solution(self):
        self._solutions = [] #track the top few (obj,soln_no) pairs
        self._solution_number = 0 #counter to differentiate solns with same objective
        self._solution_moves = {} #maps solution results to their moves
    
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
                
            #set a flag for if any lazy constraints were added
            self._lazy_constraints_added = False
                
            #run the lazy checks for every first dice roll considered
            for first_dice_roll in range(len(self._dice_rolls[0])):
                self._lazy_checks((first_dice_roll,), XV, LV)
                
            if not self._lazy_constraints_added and self._solution_count > 1:
                self._track_multiple_solutions(model, XV)
   
    """
    handles the storage of multiple solution values according to the input solution_count variable
    Adds a new solution to the list of stored solutions and adds lazy constraints to force
    infeasibility under the threshold of multiple solutions
    """
    def _track_multiple_solutions(self, model, XV):
        X = self.X
        Beta = self.Beta
        #first find the information about this solution, it's objective and the moves
        objective = model.cbGet(GRB.Callback.MIPSOL_OBJ)
        played_tiles, _ = self._get_pieces_played_in_scenario(XV, (0,)) 
        
        #create a tuple used to identify this solution and store the solution
        soln_id = (objective, self._solution_number)
        self._solution_moves[soln_id] = played_tiles 
        
        #add a constraint to rule out this solution
        model.cbLazy(quicksum(X[t,s,(0,)] for (t,s) in played_tiles) <= len(played_tiles) - 1)
        
        #add this soln to the solution list
        self._solutions.append(soln_id)
        self._solutions.sort(reverse=True)
        #if there are too many solutions now, remove one
        if len(self._solutions) > self._solution_count:
            self._solutions.pop()
        #if there are the correct number of solutions, add a lower bound to the objective value
        #to force infeasibility if anything lower than these solutions is reached
        if len(self._solutions) == self._solution_count:
            model.cbLazy(Beta >= self._solutions[-1][0])
        self._solution_number += 1 #increment the secondary counter 
         
    """
    find the pieces that are missing given the played tiles and the expected count for pieces
    """
    def _find_missing_pieces(self, played_tiles, expected_piece_counts):
        #next check using the played tiles that enough have been played
        answer_counts = {}
        for tile, square in played_tiles:
            answer_counts[tile.get_piece()] = answer_counts.get(tile.get_piece(),0) + 1
            
        #check through and ensure enough have been played and track any pieces that are missing
        missing_pieces = []
        for piece in expected_piece_counts:
            if expected_piece_counts[piece] > answer_counts.get(piece,0):
                missing_pieces += [piece]
        return missing_pieces
    
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
    returns True if one of the missing_pieces can be played on the board, False if they cannot
    """
    def _can_place_a_missing_piece(self, missing_pieces):
        #now for every missing piece, we need to check if there is absolutely anywhere it could go
        for piece in missing_pieces:
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
                                    self._lazy_constraints_added = True
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
    def _add_any_isolated_placement_lazy_constraints(self, scenario, played_tiles):
        m = self.m
        S = self.S
        T = self.T
        X = self.X
        
        #check if the played tiles are valid placements, i.e have connections to the board
        tilesToAdd = list(played_tiles) #copy the played tiles to a list for adding to the board
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
            self._lazy_constraints_added = True #set the flag for having added a lazy constraint
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
        S = self.S
        T = self.T
        X = self.X #retrieve the X variables
        
        played_tiles, piece_counts = self._get_pieces_played_in_scenario(XV, scenario)
        
        if self._isolated_pieces == "lazy":            
            isolatedPieces = self._add_any_isolated_placement_lazy_constraints(scenario, played_tiles)
        else:
            isolatedPieces = False
                                                
        #if there were no isolated pieces, then all pieces were added to the board in the earlier process
        if Piece.BASIC not in piece_counts:
            missing_pieces = self._find_missing_pieces(played_tiles, piece_counts)
            
            canPlaceMissingPiece = self._can_place_a_missing_piece(missing_pieces)
            if canPlaceMissingPiece:
                m.cbLazy(1 <= quicksum(1 - X[t,s,cc] for t in T for s in S for cc in prefixes(scenario) if cc != tuple() and XV[t,s,cc] > 0.9) +
                              quicksum(X[t,s,cc] for t in T for s in S for cc in prefixes(scenario) if cc != tuple() and XV[t,s,cc] < 0.1))
                self._lazy_constraints_added = True #set the flag
        else:
            canPlaceMissingPiece = False #don't consider the missing piece idea when playing generic pieces, it doesn't make sense
         
        #finally we also want to check for any loops for longest paths
        if self._longest_paths and self._path_loops == "lazy":
            self._add_any_loop_lazy_constraints(scenario, LV)
            
        #if we haven't added any lazy constraints for this scenario, do the checks for all the child scenarios
        #also don't do any recursion if doing a linear_tree because there is only one step of integer
        if not canPlaceMissingPiece and not isolatedPieces and len(scenario) < len(self._dice_rolls) and not self._linear_tree:
            for nextRoll in range(len(self._dice_rolls[len(scenario)])):
                self._lazy_checks(scenario + (nextRoll,), XV, LV)
            
        #remove the tiles from the board
        for tile, square in played_tiles:
            self._board.remove_tile(square)
            
    """
    uses the values in the model to determine which pieces are played in each scenario.
    Returns the (tile, square) pairs of played tiles, and the counts of all pieces that need to be played
    """
    def _get_pieces_played_in_scenario(self, XV, scenario):
        I = self.I
        #find the pieces that need to be played in this scenario and the corresponding tiles
        piece_counts = self._dice_rolls[len(scenario)-1][scenario[-1]].get_dice()
        tilesToCheck = []
        for piece in piece_counts:
            tilesToCheck += Tile.get_variations(piece)
        if self._specials:
            for piece in SPECIAL_PIECES:
                tilesToCheck += Tile.get_variations(piece)
        
        #search through the current solution to see which pieces have been played
        played_tiles = []
        for s in I:
            for tile in tilesToCheck:
                if XV[tile,s,scenario] > 0.9:
                    played_tiles += [(tile,s)]
        return played_tiles, piece_counts
        
    
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
    
    
"""
ensures that there is an empty folder located at 'folder', deleting any existing folder if there is one
"""       
def create_empty_folder(folder):

    #if the folder we are logging to exists, delete it
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        pass #if the folder wasn't there, we don't mind
    
    #then create an empty directory there, using makedirs to make any required folders along the way
    os.makedirs(folder)  
    
        
if __name__ == "__main__":
    #board = rulebook_game()
    #dice_rolls = rulebook_dice_rolls()
    #dice_rolls = [[DiceRoll({Piece.BASIC : 3, Piece.JUNCTION : 1},1)]]
    
    #perfect game calculation
#    board = Board()
#    dice_rolls = [[DiceRoll({Piece.BASIC : 21, Piece.JUNCTION : 7},1,3)]]
#    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", )
#    s.solve(print_output=True, printD="all")
    
    board = Board()
    dice_rolls = [[DiceRoll({Piece.HIGHWAY_CORNER : 1, Piece.RAILWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 1, 0)],
                   [DiceRoll({Piece.BASIC : 18, Piece.JUNCTION : 6}, 1, 3)]]
    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", )
    s.solve(print_output=True, printD="all")
    
#    board = Board()
#    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.R270), (0,2), 1)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.I), (1,2), 1)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT,Rotation.R90), (1,0), 1)
#    board.add_tile(Tile(Piece.CORNER_STATION,Rotation.R90), (0,1), 1)
#    board.add_tile(Tile(Piece.CORNER_STATION,Rotation.R90), (5,6), 2)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT,Rotation.R90), (1,1), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER,Rotation.R90), (0,5), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER,Rotation.R270), (0,6), 2)
#    board.add_tile(Tile(Piece.RAILWAY_T,Rotation.R90), (1,3), 3)
#    board.add_tile(Tile(Piece.OVERPASS,Rotation.I), (1,6), 3)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT,Rotation.I), (0,3), 3)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT,Rotation.I), (6,5), 3)
#    board.add_tile(Tile(Piece.OVERPASS,Rotation.I), (2,6), 4)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.R90), (2,3), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER,Rotation.R270), (4,6), 4)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT,Rotation.R90), (2,4), 4)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.R270), (2,5), 5)
#    board.add_tile(Tile(Piece.HIGHWAY_T,Rotation.I), (3,6), 5)
#    board.add_tile(Tile(Piece.CORNER_JUNCTION,Rotation.R180), (4,5), 5)
#    board.add_tile(Tile(Piece.OVERPASS,Rotation.R90), (3,5), 5)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER,Rotation.R180), (3,4), 5)
#    board.add_tile(Tile(Piece.THREE_H_JUNCTION,Rotation.R270), (4,4), 6)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT,Rotation.R90), (1,5), 6)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.R270), (5,0), 6)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.R90), (6,0), 6)
#    board.add_tile(Tile(Piece.CORNER_STATION,Rotation.R270), (6,1), 6)
    
#    dice_rolls = rulebook_dice_rolls()
#    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", )
#    s.solve(print_output=True, printD="all")
    
#    board = Board()
#    dice_rolls = rulebook_dice_rolls()
#    #dice_rolls = [[DiceRoll({Piece.STRAIGHT_STATION : 1, Piece.RAILWAY_CORNER : 1, 
#    #                         Piece.RAILWAY_T : 1, Piece.HIGHWAY_T : 1},1)]]
#    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", linear=True, old_constraints=True)
#    s.solve(print_output=True, printD="all")
    
    #board = Board()
#    dice_rolls = [[DiceRoll({Piece.RAILWAY_STRAIGHT : 1}, 1)],
#                   [DiceRoll({Piece.RAILWAY_STRAIGHT : 1}, 1)]]
#    #s = RailroadInkSolver(board, 1, dice_rolls, "open-ends", specials=False, isolated_pieces="relief")
#    s = RailroadInkSolver(board, 1, dice_rolls, "expected-score", specials=False, isolated_pieces="relief")
#    s.solve(folder="test", print_output=True, printD="all")

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
#    s.solve(folder="test", print_output=True, printD="all")  
    
    
    
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
#    dice_rolls = [[DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.OVERPASS : 1,
#                              Piece.HIGHWAY_CORNER : 1, Piece.HIGHWAY_STRAIGHT : 1}, 1)]]
#    
#    dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
#                                 Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
#                      [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
#                                 Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 1)],
#                    [DiceRoll({Piece.HIGHWAY_CORNER : 1, Piece.RAILWAY_STRAIGHT : 2,
#                               Piece.CORNER_STATION : 1}, 1)],
#                    [DiceRoll({Piece.RAILWAY_STRAIGHT : 2, Piece.HIGHWAY_STRAIGHT : 1,
#                               Piece.CORNER_STATION : 1}, 1)],
#                    [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.OVERPASS : 1,
#                               Piece.HIGHWAY_CORNER : 1, Piece.HIGHWAY_STRAIGHT : 1}, 1)],
#                    [DiceRoll({Piece.HIGHWAY_STRAIGHT : 2, Piece.HIGHWAY_T : 1,
#                               Piece.CORNER_STATION : 1}, 1)]]
#    
#    #dice_rolls = [[DiceRoll({}, 1)]]
    
#    dice_roll = [[DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.OVERPASS : 1,
#                            Piece.HIGHWAY_CORNER : 1, Piece.HIGHWAY_STRAIGHT : 1}, 1)],
#                [DiceRoll({Piece.BASIC : 3, Piece.JUNCTION : 1})]]
#
#    #s = RailroadInkSolver(board, 6, dice_rolls, "expected-score", internal_sinks=True)
#    s = RailroadInkSolver(board, 6, dice_rolls, "expected-score", solution_count=5)
#    s.solve(print_output=True)