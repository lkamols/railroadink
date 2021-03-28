
from gurobipy import *
from board import *
import csv
import numpy as np


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
    output - whether to print Gurobi output
    printing - whether to print the result
    """
    def solve(self, resultsFile=None, output=0, printing=False):
        
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
        #for ease, create entries in the opposite direction that point to the same variables
        #e.g Y[s,ss,e,d] = Y[ss,s,e,d] for all values
        Y = {}
        for s in S:
            for e in E:
                for d in D:
                    for ss in self._board.adjacents(s, forward = True):
                        Y[s,ss,e,d] = m.addVar(vtype=GRB.BINARY)
                        Y[ss,s,e,d] = Y[s,ss,e,d]
        
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
        #whether square s is an end square of the path
        K = {(s,e,d) : m.addVar(vtype=GRB.BINARY) for s in I for e in E for d in D} 
        #whether there is a longest path connection between squares s and ss
        #define this similarly to the Y variables in that two references to the same variable exist
        L = {}
        for s in I:
            for e in E:
                for d in D:
                    for ss in self._board.adjacents(s, forward = True, internal=True):
                        L[s,ss,e,d] = m.addVar(vtype=GRB.BINARY)
                        L[ss,s,e,d] = L[s,ss,e,d]
        #whether square s counts towards the "e" longest road
        M = {(s,e,d) : m.addVar(vtype=GRB.BINARY) for s in I for e in E for d in D}
        
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
                                 for t in Tile.get_variations(p)) <= 
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
            
        #there must be a connection to a piece played earlier or on this turn
        earlier_move_connection = {(t,s,c) :
            m.addConstr(X[t,s,c] <= (quicksum(X[tt,(s[0],s[1]-1),cc] for tt in T if tt.get_edge_type_on_side(Side.RIGHT) == t.get_edge_type_on_side(Side.LEFT) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.LEFT) != EdgeType.B and (s[0],s[1]-1) in S) else 0) +
                                     (quicksum(X[tt,(s[0],s[1]+1),cc] for tt in T if tt.get_edge_type_on_side(Side.LEFT) == t.get_edge_type_on_side(Side.RIGHT) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.RIGHT) != EdgeType.B and (s[0],s[1]+1) in S) else 0) + 
                                     (quicksum(X[tt,(s[0]-1,s[1]),cc] for tt in T if tt.get_edge_type_on_side(Side.BOTTOM) == t.get_edge_type_on_side(Side.TOP) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.TOP) != EdgeType.B and (s[0]-1,s[1]) in S) else 0) + 
                                     (quicksum(X[tt,(s[0]+1,s[1]),cc] for tt in T if tt.get_edge_type_on_side(Side.TOP) == t.get_edge_type_on_side(Side.BOTTOM) for cc in prefixes(c)) 
                                            if (t.get_edge_type_on_side(Side.BOTTOM) != EdgeType.B and (s[0]+1,s[1]) in S) else 0))
            for t in T for s in S for c in C if c != tuple()}
        
            
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
            for s in S for ss in self._board.adjacents(s) for e in E for d in D}
            
        #transfer flow existence, if the piece played is a junction, we can flow between highways and railways on that square
        transfer_flow = {(s,e,d):
            m.addConstr(FF[s,e,d] <= NUM_STARTS * quicksum(X[t,s,c] for t in T if t.get_piece() in SWITCH_PIECES for c in prefixes(d)))
            for s in I for e in E for d in D}
            
        #add a bonus point if there is only one connection to the super sink (all exits connected)
        bonus_point = {d :
            m.addConstr((NUM_STARTS - 1)*J[d] <= quicksum((1 - H[s,d]) for s in O))
            for d in D}
            
        #LONGEST RAILWAY/HIGHWAY CONSTRAINTS
        #these are only calculated for the full scenarios
        two_ends = {(e,d) :
            m.addConstr(quicksum(K[s,e,d] for s in I) == 2)
            for e in E for d in D}
            
        #an edge can only score points if it is a start square and has one out connection or has two directional connections
        inflow = {(s,e,d) :
            m.addConstr(2*M[s,e,d] == K[s,e,d] + quicksum(L[s,ss,e,d] for ss in self._board.adjacents(s, internal=True)))
            for s in I for e in E for d in D}
            
        #there can only be flow on edges that have a connection of that type
        only_on_connected_edges = {(s,ss,e,d) :
            m.addConstr(L[s,ss,e,d] <= Y[s,ss,e,d])
            for s in I for ss in self._board.adjacents(s, internal=True, forward=True) for e in E for d in D}

        #this formulation allows for completely separate loops, handle removal in lazy constraints
        #except for basic size 4 loops, add all of those at the start because they are likely to get added
        no_size_4_loops = {((r,c),e,d) :
            m.addConstr(L[(r,c),(r,c+1),e,d] + L[(r,c),(r+1,c),e,d] +
                        L[(r,c+1),(r+1,c+1),e,d] + L[(r+1,c),(r+1,c+1),e,d] <= 3)
            for r in range(NUM_ROWS-1) for c in range(NUM_COLS-1) for e in E for d in D}
            
        #don't set a start location and not have it scoring, this may be redundant with the two_ends equality
        end_bounds = {(s,e,d) :
            m.addConstr(K[s,e,d] <= M[s,e,d])
            for s in I for e in E for d in D}
            
        #SCORING CONSTRAINTS
        #calculate the score for each full scenario, use a <= because the optimisation will force equality where important
        scoring = {d :
            m.addConstr(Alpha[d] <= quicksum(X[t,s,c] for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)) #centre square points
                                  + 48 - 4 * quicksum(H[s,d] for s in O) #join cluster points
                                  + J[d] #bonus point
                                  + quicksum(M[s,e,d] for s in I for e in E) #longest path points
                                  - quicksum(X[t,s,c] * t.loose_ends(s) for t in T for s in I for c in prefixes(d)) #subtraction for the number of loose ends (start of penalty calculation)
                                  + quicksum(Y[s,ss,e,dd] for (s,ss,e,dd) in Y if dd == d and s in I and ss in I) #these points are not lost if there is a join on that edge
            )
            for d in D}
            
        if self._objective == "expected-score":
            m.setObjective(quicksum(Alpha[d] for d in D), GRB.MAXIMIZE)
            
        m.setParam('OutputFlag', output)
            
            
        #set up requirements for the use of lazy constraints
        m.setParam('MIPGap', 0)
        m.setParam('LazyConstraints', 1)
        
        #anything that is needed in the callback needs to be added to the model
        m._X = X 
        m._L = L
        m._dice_rolls = self._dice_rolls
        m._I = I
        m._S = S
        m._T = T
        m._E = E
        m._board = self._board
        #optimize
        m.optimize(callback)

        if printing:
            self._print_result(m, X, C)
        
        #print the results to a CSV
        if resultsFile != None:
            with open(resultsFile, mode="w", newline="") as csv_file:
                csv_writer = csv.writer(csv_file, delimiter=",")
                csv_writer.writerow(["Turn {0}".format(self._turn + i) for i in range(len(self._dice_rolls))] + 
                                     ["Score", "Connecting Exits", "Longest Railway", "Longest Highway", "Centre Points", "Errors", "Bonus Point"])
                for d in D:
                    score = round(Alpha[d].x)
                    centre_points = round(sum(X[t,s,c].x for s in I if Board.is_centre_square(s) for t in T for c in prefixes(d)))
                    connecting_exits = round(48 - 4 * sum(H[s,d].x for s in O))
                    longest_railway = round(sum(M[s,EdgeType.R,d].x for s in I))
                    longest_highway = round(sum(M[s,EdgeType.H,d].x for s in I))
                    errors = round(-1* sum(X[t,s,c].x * t.loose_ends(s) for t in T for s in I for c in prefixes(d))
                                  + sum(Y[s,ss,e,dd].x for (s,ss,e,dd) in Y if dd == d and s in I and ss in I))
                    bonus_point = round(J[d].x)
                    csv_writer.writerow([turn for turn in d] + [score, connecting_exits, longest_railway, 
                                                                longest_highway, centre_points, errors, bonus_point])
        return round(m.objVal)
                    
                
 
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
        
"""
The callback used in the Railroad Ink solver
"""    
def callback(model, where):
    if where == GRB.Callback.MIPSOL:
        #get the X and L values in the solution
        XV = {k : v for (k,v) in zip(model._X.keys(), model.cbGetSolution(list(model._X.values())))}
        LV = {k : v for (k,v) in zip(model._L.keys(), model.cbGetSolution(list(model._L.values())))}
        #run the lazy checks for every first dice roll considered
        for first_dice_roll in range(len(model._dice_rolls[0])):
            lazy_checks(model, model._board, (first_dice_roll,), XV, LV)
        
"""
find the pieces that are missing given the played tiles and the expected count for pieces
"""
def find_missing_pieces(playedTiles, expectedPieceCounts):
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
def valid_placement(model, board, tile, s):
    #a placement is valid if there is any connection to another piece and no invalid connections
    connections = 0
    clashed = False
    for side in Side:
        newEdgeType = tile.get_edge_type_on_side(side)
        #check if that side is blank
        if newEdgeType != EdgeType.B:
            #get the opposite side
            oppS, oppSide = Board.opposite_edge(s,side)
            #now check if the opposite side exists and if there is a connection or a clash there
            if oppS in model._S:
                existingEdgeType = board.get_tile_at(oppS).get_edge_type_on_side(oppSide)
                if existingEdgeType == newEdgeType:
                    connections += 1
                elif existingEdgeType == EdgeType.clash_type(newEdgeType):
                    return False #there is a clash, we cannot play this piece here
    return (connections > 0) #we can play a piece if there was at least one connection, otherwise we can't


"""
returns True if one of the missingPieces can be played on the board, False if they cannot
"""
def can_place_a_missing_piece(model, board, missingPieces):
    #now for every missing piece, we need to check if there is absolutely anywhere it could go
    for piece in missingPieces:
        variations = Tile.get_variations(piece) #get the possible orientations
        #check to see if there is anywhere this piece could be placed
        for s in model._I:
            if board.is_square_free(s):
                #check every variation of the tile
                for tile in variations:
                    #if this placement is valid, then there is a valid placement
                    if valid_placement(model, board, tile, s):
                        return True           
    return False #we found no placement for any missing piece

"""
determines if there are any loops in this solution and adds lazy constraints if there are any
d is the scenario of dice rolls we received
"""
def add_any_loop_lazy_constraints(model, d, LV):
    if len(d) == len(model._dice_rolls): #we are on the final roll
        #use the existing board and check for loops, start by looking for any top left corners, as every loop has to have 
        #a top left connection both to the right and down from one square
        for r in range(NUM_ROWS - 1): #cannot have a loop starting in the last row (or col)
            for c in range(NUM_COLS - 1):
                for e in model._E:
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
                                model.cbLazy(len(squares) - 2 >= quicksum(model._L[squares[i],squares[i+1],e,d] for i in range(len(squares)-1)))
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
def lazy_checks(model, board, scenario, XV, LV):
    
    X = model._X #retrieve the X variables
    
    #find the pieces that need to be played in this scenario and the corresponding tiles
    pieceCounts = model._dice_rolls[len(scenario)-1][scenario[-1]].get_dice()
    tilesToCheck = []
    for piece in pieceCounts:
        tilesToCheck += Tile.get_variations(piece)
    for piece in SPECIAL_PIECES:
        tilesToCheck += Tile.get_variations(piece)
    
    #search through the current solution to see which pieces have been played
    playedTiles = []
    for s in model._I:
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
            if valid_placement(model, board, tile, s):
                #if this is a valid placement on the board, add it to the board and remove it from the 
                #list of tiles we need to add
                board.add_tile(tile, s)
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
                    if oppS in model._S and oppS not in isolatedSquares:
                        connectionPoints += [(oppS, oppSide, tile.get_edge_type_on_side(side))]
        
        model.cbLazy(1 <= quicksum(1 - X[t,s,scenario] for (t,s) in tilesToAdd) #can remove an isolated tile
                        + quicksum(X[t,s,c] for (s, side, edgeType) in connectionPoints  #all connection pieces on any prior scenario
                                            for c in prefixes(scenario) if c != tuple()
                                            for t in model._T if t.get_edge_type_on_side(side) == edgeType))
        #then add these to the board when checking for if pieces are missing
        for tile, s in tilesToAdd:
            board.add_tile(tile, s)
        #set a flag for if there were isolated placements
        isolatedSquareConstraintsAdded = True
        
    
    
    #if there were no isolated pieces, then all pieces were added to the board in the earlier process
    missingPieces = find_missing_pieces(playedTiles, pieceCounts)
    
    canPlaceMissingPiece = can_place_a_missing_piece(model, board, missingPieces)
    if canPlaceMissingPiece:
        model.cbLazy(1 <= quicksum(1 - X[t,s,scenario] for (t,s) in playedTiles) #we can move an already played tile
                        + quicksum(X[t,s,scenario] for piece in missingPieces for t in Tile.get_variations(piece) for s in model._I) #play a missing piece
                        + (quicksum(X[t,s,scenario] for piece in SPECIAL_PIECES for t in Tile.get_variations(piece) for s in model._I) 
                                if not board.all_specials_used() else 0)) #play a special piece
        
    #finally we also want to check for any loops for longest paths
    add_any_loop_lazy_constraints(model, scenario, LV)

     
    #if we haven't added any lazy constraints for this scenario, do the checks for all the child scenarios
    if not canPlaceMissingPiece and not isolatedSquareConstraintsAdded and len(scenario) < len(model._dice_rolls):
        for nextRoll in range(len(model._dice_rolls[len(scenario)])):
            lazy_checks(model, board, scenario + (nextRoll,), XV, LV)
        
    #remove the tiles from the board
    for tile, square in playedTiles:
        board.remove_tile(square)
    
        
if __name__ == "__main__":
    board = rulebook_game()
    dice_rolls = rulebook_dice_rolls()
    s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
    s.solve(resultsFile="results.csv", output=1, printing=True)
    
#    board = Board()
#    dice_rolls = rulebook_dice_rolls()
#    s = RailroadInkSolver(board, 1, dice_rolls + dice_rolls + dice_rolls + dice_rolls + dice_rolls + dice_rolls + dice_rolls, "expected-score")
#    s.solve(resultsFile="results2.csv")
    