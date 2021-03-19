
from gurobipy import *
from board import *
import csv


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
    generates all possible scenarios using the dice rolls.
    currentList - the current scenario 
    L - list of all final scenarios
    V - list of every step in every scenario
    to generate all possible scenarios, call with self._generate_scenarios([], L, V) with L, V initialise as []
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
    resultsFile - if not None, will create a csv with information about the problem
    """
    def solve(self, resultsFile=None):
        
        #SETS
        
        I = {(i,j) for i in range(NUM_ROWS) for j in range(NUM_COLS)} #inside squares
        O = Board.get_start_squares() #outside squares
        S = I.union(O) #all squares
        
        T = Tile.get_all_variations() #all possible tiles
        E = [EdgeType.H, EdgeType.R] #the two edge types
        
        
        C = [] #every individual step of a scenario possible
        D = [] #all the final (Last) scenarios / dice rolls
        self._generate_scenarios([], D, C)
        
        m = Model("railroad-ink") #create the model
        
        #BASIC PLACEMENT VARIABLES
        #x variables for whether tile t is placed at square s in the most recent turn of scenario c
        #x variables exist for every step of every scenario, which turn is defined by the length
        #of the tuple c, e.g if the tuple is () they are default placements, (1), they are first (since started)
        #move placements
        X = {(t,s,c) : m.addVar(vtype=GRB.BINARY) for t in T for s in S for c in C}
        #y variables for whether there is a link between adjacent squares with edge type e with dice rolls d
        #these variables are only calculated at the end of the scenarios, not during
        Y = {(s,ss,e,d) : m.addVar(vtype=GRB.BINARY) 
                for s in S for ss in self._board.adjacents(s, forward=True) for e in E for d in D}
        
        #CONNECTING START POINTS VARIABLES
        #each of these is defined for every single possible set of dice rolls d in D
        #the flow of joins between two adjacent squares
        F = {(s,ss,e,d): m.addVar() for s in S 
                for ss in self._board.adjacents(s) for e in E for d in D}
        #transfer flow between rails and highways at square s (from e)
        FF = {(s,e,d) : m.addVar() for s in I for e in E for d in D} 
        #flow from a start square to the super sink
        G = {(s,d) : m.addVar() for s in O for d in D} 
        #whether there is any flow from a start square to the super sink
        H = {(s,d) : m.addVar(vtype=GRB.BINARY) for s in O for d in D} 
        #whether the extra point for connecting all of them is earned
        J = {d : m.addVar(vtype=GRB.BINARY) for d in D}
        
        #LONGEST RAILWAY/HIGHWAY VARIABLES
        #each of these is defined for every single possible set of dice rolls d in D
        #whether square s is the start square
        K = {(s,e,d) : m.addVar(vtype=GRB.BINARY) for s in I for e in E for d in D} 
        #longest path flow from s1 to s2 of type e
        L = {(s,ss,e,d): m.addVar() for s in I
                for ss in self._board.adjacents(s, internal=True) for e in E for d in D} 
        #whether there is any longest path from from s1 to s2 of type E permitted
        M = {(s,ss,d): m.addVar(vtype=GRB.BINARY) for s in I
                for ss in self._board.adjacents(s, internal=True) for e in E for d in D} 
        #whether square s counts towards the "e" longest road
        N = {(s,d) : m.addVar(vtype=GRB.BINARY) for s in I for e in E for d in D}
        
        #SCORING VARIABLES
        #the score for every final scenario
        Alpha = {d : m.addVar() for d in D}
        
        #CONSTRAINTS
        
        #LEGAL CONSTRAINTS
        
        #only place one tile in each square - in all possible scenarios,
        #this means that only one tile can be placed there across all prefixes
        one_tile_per_square = {(s,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T for c in prefixes(d)) <= 1)
            for s in S for d in D}
            
        #ensure all the pieces that are already on the board are kept, and no others are placed
        #default placements have a scenario index of ()
        default_placements = {(t,s) :
            m.addConstr(X[t,s,()] == (1 if self._board.get_tile_at(s) == t else 0))
            for s in S for t in T}
            
        #on every turn, in every scenario, we can only use the moves that are allocated
        use_pieces = {(p,c) : 
            m.addConstr(quicksum(X[t,s,c] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) == 
                        (self._dice_rolls[len(c) - 1][c[-1]].get_dice().get(p, 0))) 
                        #^ this gets the dictionary of this dice roll, then searches for the piece, defaulting to zero
            for p in BASIC_PIECES + JUNCTION_PIECES + START_PIECES for c in C if c != tuple()}
    
        #play special pieces at most once each in every possible dice roll scenario
        special_once = {(p,d):
                m.addConstr(quicksum(X[t,s,c] for s in S
                        for t in Tile.get_variations(p) for c in prefixes(d)) <= 1)
                for p in SPECIAL_PIECES for d in D}
            
        #play at most one special piece per turn (in every scenario)
        one_special_per_turn = {c :
            m.addConstr(quicksum(X[t,s,c] for s in S for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=1)
            for c in C if c != tuple()}
            
        #play max 3 special pieces total, for every single set of full dice rolls
        three_specials_max = {d :
            m.addConstr(quicksum(X[t,s,c] for s in S for c in prefixes(d)
                     for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=3)
            for d in D}
            
            
        #constraints for clashes on edges joining squares horizontally, preventing railways and highways being connected
        #this needs to hold across every final scenario, only consider the final scenarios as the earlier ones are
        #accomplished using the final scenarios and are redundant to add
        horizontal_clashes = {(s,e,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e for c in prefixes(d)) +
                        quicksum(X[t,(s[0],s[1]+1),c] for t in T 
                            if t.get_edge_type_on_side(Side.LEFT) == EdgeType.clash_type(e) for c in prefixes(d)) <= 1)
            for s in S if (s[0],s[1]+1) in S for e in E for d in D}
            
        #constraints for clashes on edges joining squares vertically, preventing railways & highways connecting
        #scenario logic as for above constraints
        vertical_clashes = {(s,e,d) :
            m.addConstr(quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e for c in prefixes(d)) +
                        quicksum(X[t,(s[0]+1,s[1]),c] for t in T if t.get_edge_type_on_side(Side.TOP) == EdgeType.clash_type(e) 
                                    for c in prefixes(d)) <= 1) 
            for s in S if (s[0]+1,s[1]) in S for e in E for d in D}
            
        #constraints for if there are connections on any horizontal edges
        #Y variables only defined at the end, so they can be set if any of the X value prefixes are set
        #only define these rules for the full dice roll
        horizontal_connections = {(s,e,d)  :
            m.addConstr(2 * Y[s, (s[0], s[1]+1), e, d] <= 
                              quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e for c in prefixes(d)) +
                              quicksum(X[t,(s[0],s[1]+1),c] for t in T if t.get_edge_type_on_side(Side.LEFT) == e for c in prefixes(d)))
            for s in S if (s[0],s[1]+1) in S for e in E for d in D}
            
        #constraints for if there are connections on any vertical edges
        #scenario definition as above
        vertical_connections = {(s,e,d) :
            m.addConstr(2 * Y[s, (s[0]+1, s[1]), e, d] <=
                              quicksum(X[t,s,c] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e for c in prefixes(d)) +
                              quicksum(X[t,(s[0]+1,s[1]),c] for t in T if t.get_edge_type_on_side(Side.TOP) == e for c in prefixes(d)))
            for s in S if (s[0]+1,s[1]) in S for e in E for d in D}
        
            
        #JOINING CONSTRAINTS    
        #these are all done for only the complete dice rolls, so for d in D
        
        #the flow into an internal square must be the same as the flow out
        internal_flows = {(s,e,d) :
            m.addConstr(quicksum(F[s,ss,e,d] for ss in self._board.adjacents(s)) + FF[s,e,d] ==
                        quicksum(F[ss,s,e,d] for ss in self._board.adjacents(s)) + FF[s,EdgeType.clash_type(e),d])
            for s in I for e in E for d in D}
            
        #the flow into an external square must be the same as the flow out
        #these have a guaranteed flow in of 1 as start squares
        #they also have the ability to flow out to the sink with variable G
        external_flows = {(s,d) :
            m.addConstr(1 + quicksum(F[ss,s,e,d] for ss in self._board.adjacents(s) for e in E) ==
                        quicksum(F[s,ss,e,d] for ss in self._board.adjacents(s) for e in E) + G[s,d])
            for s in O for d in D}
            
        #the H variables must be set if there is any flow from an exit to the super sink
        sink_connections = {(s,d) : 
            m.addConstr(G[s,d] <= NUM_STARTS * H[s,d])
            for s in O for d in D}
            
        #flow variables can only be set if the connection exists on that edge
        flow_existence = {(s,ss,e,d):
            m.addConstr(F[s,ss,e,d] <= (NUM_STARTS * Y[s,ss,e,d]))
            if ss > s else #ss > s if the row or col is greater in ss (i.e moving right or down) by tuple comparison
            m.addConstr(F[s,ss,e,d] <= (NUM_STARTS * Y[ss,s,e,d]))
            for s in S for ss in self._board.adjacents(s) for e in E for d in D}
            
        #transfer flow existence, if the piece played is a junction, we can flow between highways and railways on that square
        transfer_flow = {(s,e,d):
            m.addConstr(FF[s,e,d] <= NUM_STARTS * quicksum(X[t,s,c] for t in T if t.get_piece() in SWITCH_PIECES for c in prefixes(d)))
            for s in I for e in E for d in D}
            
        #add a bonus point if there is only one connection to the super sink (all exits connected)
        bonus_point = {d :
            m.addConstr((NUM_STARTS - 1)*J[d] <= quicksum((1 - H[s,d]) for s in O))
            for d in D}
        
        
        #SCORING CONSTRAINTS
        #calculate the score for each full scenario, use a <= because the optimisation will force equality where important
        scoring = {d :
            m.addConstr(Alpha[d] <= quicksum(X[t,s,c] for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)) #centre square points
                                  + 48 - 4 * quicksum(H[s,d] for s in O) #join cluster points
                                  + J[d] #bonus point
                                  - quicksum(X[t,s,c] * t.loose_ends(s) for t in T for s in I for c in prefixes(d)) #subtraction for the number of loose ends (start of penalty calculation)
                                  + quicksum(2*Y[s,ss,e,dd] for (s,ss,e,dd) in Y if dd == d and s in I and ss in I) #these points are not lost if there is a join on that edge
            )
            for d in D}
            
        m.setObjective(quicksum(Alpha[d] for d in D), GRB.MAXIMIZE)
            
        #optimize
        m.optimize()

        self._print_result(m, X, C)
        
        #print the results to a CSV
        if resultsFile != None:
            with open(resultsFile, mode="w", newline="") as csv_file:
                csv_writer = csv.writer(csv_file, delimiter=",")
                csv_writer.writerow(["Turn {0}".format(self._turn + i) for i in range(len(self._dice_rolls))] + 
                                     ["Score", "Connecting Exits", "Centre Points", "Errors", "Bonus Point"])
                for d in D:
                    score = round(Alpha[d].x)
                    centre_points = round(sum(X[t,s,c].x for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)))
                    connecting_exits = round(48 - 4 * sum(H[s,d].x for s in O))
                    bonus_point = round(J[d].x)
                    errors = round(-1* sum(X[t,s,c].x * t.loose_ends(s) for t in T for s in I for c in prefixes(d))
                                  + sum(2*Y[s,ss,e,dd].x for (s,ss,e,dd) in Y if dd == d and s in I and ss in I))
                    csv_writer.writerow([turn for turn in d] + [score, connecting_exits, centre_points, errors, bonus_point])
                    
                
 
    """
    print the board with the solution attached
    """
    def _print_result(self, m, X, C):
        #find all the pieces and placements that we made and add them to the board
        for t, s, c in X:
            if c != tuple() and X[t,s,c].x > 0.9:
                self._board.add_tile(t, s, self._turn - 1 + len(c))
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print()
        
if __name__ == "__main__":
    board = rulebook_game()
    dice_rolls = rulebook_dice_rolls()
    s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
    s.solve(resultsFile="results.csv")