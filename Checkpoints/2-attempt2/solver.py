
from gurobipy import *
from board import *

"""
class containing all the tools required to solve the final move of a railroad ink game
"""
class LastMoveSolver:
    
    """
    Constructor.
    To understand a game, we need a board and the available moves
    """
    def __init__(self, board, moves):
        self._board = board
        self._moves = moves
       
    """
    create and solve an IP that gives the solution to the railroad ink problem
    """
    def solve(self):
        m = Model("railroad-ink")
        
        #SETS
        I = {(i,j) for i in range(NUM_ROWS) for j in range(NUM_COLS)}
        O = Board.get_start_squares()
        S = I.union(O)
        T = Tile.get_all_variations()
        E = [EdgeType.H, EdgeType.R]
        
        #BASIC PLACEMENT VARIABLES
        #x variables are for whether move m is made at square s
        X = {(t,s) : m.addVar(vtype=GRB.BINARY) for t in T for s in S}
        #y variables for whether there is a link between two adjacent squares with edge type e
        #note that these only go right and down (increasing row/col)
        Y = {(s,ss,e) : m.addVar(vtype=GRB.BINARY)
             for s in S for ss in self._board.adjacents(s, forward=True) for e in E}
        
        #CONNECTING START POINTS VARIABLES
        #the flow of joins between two adjacent squares
        F = {(s,ss,e): m.addVar() for s in S 
                for ss in self._board.adjacents(s) for e in E}
        #transfer flow between rails and highways at square s (from e)
        FF = {(s,e) : m.addVar() for s in I for e in E} 
        #flow from a start square to the super sink
        G = {s : m.addVar() for s in O} 
        #whether there is any flow from a start square to the super sink
        H = {s : m.addVar(vtype=GRB.BINARY) for s in O} 
        #whether the extra point for connecting all of them is earned
        J = m.addVar(vtype=GRB.BINARY)
        
        #LONGEST RAILWAY/HIGHWAY VARIABLES
        #whether square s is the start square
        A = {(s,e) : m.addVar(vtype=GRB.BINARY) for s in I for e in E} 
        #longest path flow from s1 to s2 of type e
        B = {(s,ss,e): m.addVar() for s in I
                for ss in self._board.adjacents(s, internal=True) for e in E} 
        #whether there is any longest path from from s1 to s2 of type E permitted
        C = {(s,ss,e): m.addVar(vtype=GRB.BINARY) for s in I
                for ss in self._board.adjacents(s, internal=True) for e in E} 
        #whether square s counts towards the "e" longest road
        D = {(s,e) : m.addVar(vtype=GRB.BINARY) for s in I for e in E} 
        
        #CONSTRAINTS
        
        #LEGAL CONSTRAINTS
        
        #only place one tile in each square
        one_tile_per_square = {s :
            m.addConstr(quicksum(X[t,s] for t in T) <= 1)
            for s in S}
                   
        #ensure all the pieces that are part of the board are kept
        default_placements = {s :
            m.addConstr(X[self._board.get_tile_at(s),s] == 1)
            for s in S if not self._board.is_square_free(s)}
            
        #use all of the pieces required to be used
        use_pieces = {p : 
            m.addConstr(quicksum(X[t,s] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) == 
                        (self._moves[p] if p in self._moves else 0))
            for p in BASIC_PIECES + JUNCTION_PIECES + START_PIECES}
            
        #play special pieces at most once each
        special_once = {p:
                m.addConstr(quicksum(X[t,s] for s in S for t in Tile.get_variations(p))<=1)
                for p in SPECIAL_PIECES}
            
        #play at most one special piece this turn  
        one_special_per_turn = m.addConstr(quicksum(X[t,s] for s in S if self._board.is_square_free(s)
                     for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=1)

        #play max 3 special pieces total
        three_specials_max = m.addConstr(quicksum(X[t,s] for s in S
                     for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=3)
            
        
        #constraints for clashes on edges joining squares horizontally, preventing railways and highways being connected
        horizontal_clashes = {(s,e) :
            m.addConstr(quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                        quicksum(X[t,(s[0],s[1]+1)] for t in T 
                            if t.get_edge_type_on_side(Side.LEFT) == EdgeType.clash_type(e)) <= 1)
            for s in S if (s[0],s[1]+1) in S for e in E}
            
        #constraints for clashes on edges joining squares vertically, preventing railways & highways connecting
        vertical_clashes = {(s,e) :
            m.addConstr(quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                        quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == EdgeType.clash_type(e))
                        <= 1) for s in S if (s[0]+1,s[1]) in S for e in E}
        
        
        #constraints for if there are connections on any horizontal edges
        horizontal_connections = {(s,e)  :
            m.addConstr(2 * Y[s, (s[0], s[1]+1), e] <= 
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                              quicksum(X[t,(s[0],s[1]+1)] for t in T if t.get_edge_type_on_side(Side.LEFT) == e))
            for s in S if (s[0],s[1]+1) in S for e in E}
        
        #constraints for if there are connections on any vertical edges
        vertical_connections = {(s,e) :
            m.addConstr(2 * Y[s, (s[0]+1, s[1]), e] <=
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                              quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == e))
            for s in S if (s[0]+1,s[1]) in S for e in E}
            

        #JOINING CONSTRAINTS    
        
        #the flow into an internal square must be the same as the flow out
        internal_flows = {(s,e) :
            m.addConstr(quicksum(F[s,ss,e] for ss in self._board.adjacents(s)) + FF[s,e] ==
                        quicksum(F[ss,s,e] for ss in self._board.adjacents(s)) + FF[s,EdgeType.clash_type(e)])
            for s in I for e in E}
            
        external_flows = {s :
            m.addConstr(1 + quicksum(F[ss,s,e] for ss in self._board.adjacents(s) for e in E) ==
                        quicksum(F[s,ss,e] for ss in self._board.adjacents(s) for e in E) + G[s])
            for s in O}
            
        sink_connections = {s : 
            m.addConstr(G[s] <= NUM_STARTS * H[s])
            for s in O}
            
        #flow variables can only be set if the connection exists on that edge
        flow_existence = {(s,ss,e):
            m.addConstr(F[s,ss,e] <= (NUM_STARTS * Y[s,ss,e]))
            if ss > s else #ss > s if the row or col is greater in ss (i.e moving right or down) by tuple comparison
            m.addConstr(F[s,ss,e] <= (NUM_STARTS * Y[ss,s,e]))
            for s in S for ss in self._board.adjacents(s) for e in E}
            
        #transfer flow existence, if the piece played is a junction, we can flow between highways and railways on that square
        transfer_flow = {(s,e):
            m.addConstr(FF[s,e] <= NUM_STARTS * quicksum(X[t,s] for t in T if t.get_piece() in SWITCH_PIECES))
            for s in I for e in E}
            
        bonus_point = m.addConstr((NUM_STARTS - 1)*J <= quicksum((1 - H[s]) for s in H))
        
        #LONGEST RAILWAY/HIGHWAY CONSTRAINTS
        
        #there can only be one start square for both the highway and railway
        one_start = {e :
            m.addConstr(quicksum(A[s,e] for s in I) == 1)
            for e in E}
            
        #we can only let a longest path travel on an edge which is connected
        #flow variables can only be set if the connection exists on that edge
        path_flow_existence = {(s,ss,e):
            m.addConstr(C[s,ss,e] <= Y[s,ss,e])
            if ss > s else
            m.addConstr(C[s,ss,e] <= Y[ss,s,e])
            for s in I for ss in self._board.adjacents(s, internal=True) for e in E}
            
        #the inflow of the longest high/railway must be greater than the outflow of the longest high/railway
        #the scoring component saps from the flow in order to score, preventing cycles
        #the start piece is not bound by the inflow
        path_flow = {(s,e) :
            m.addConstr(quicksum(B[ss,s,e] for ss in self._board.adjacents(s, internal=True)) + LONGEST_POSSIBLE_PATH * A[s,e] >=
                        quicksum(B[s,ss,e] for ss in self._board.adjacents(s, internal=True)) + D[s,e])
            for s in I for e in E}
            
            
        #to restrict the longest pathway to not branch, we use the C variables, only allow flow if it is permitted by the C variables
        no_branching = {(s,ss,e) :
            m.addConstr(B[s,ss,e] <= LONGEST_POSSIBLE_PATH * C[s,ss,e])
            for s in I for ss in self._board.adjacents(s, internal=True) for e in E}
            
        one_outflow_per_square = {(s,e) :
            m.addConstr(quicksum(C[s,ss,e] for ss in self._board.adjacents(s, internal=True)) <= 1)
            for s in I for e in E}
        
         
        #OBJECTIVE FUNCTION
        #set the objective function
        m.setObjective(quicksum(X[t,s] for s in I if Board.is_centre_square(s) for t in T) #centre square points
                    + 48 - 4 * quicksum(H[s] for s in H) #joined cluster points
                    + quicksum(D[s,e] for s in I for e in E) #longest path points
                    - quicksum(X[t,s] * t.loose_ends(s) for t in T for s in I) #subtraction for the number of loose ends (start of penalty calculation)
                    + quicksum(2*Y[s,ss,e] for (s,ss,e) in Y if s in I and ss in I) #these points are not lost if there is a join on that edge
                    + J #the bonus point for connecting all of them together
                , GRB.MAXIMIZE)
            
        #optimize
        m.optimize()

        self._print_result(m, X, Y, F, G, H, J, A, B, C, D, T, S, I, E)
 
    """
    print the board with the solution attached
    """
    def _print_result(self, m, X, Y, F, G, H, J, A, B, C, D, T, S, I, E):
        #find all the pieces and placements that we had and add them to the board
        for t, s in X:
            if X[t,s].x > 0.9 and self._board.is_square_free(s):
                self._board.add_solution_tile(s[0], s[1], t)
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print()
        
        #next print out the resulting score
        print("The total points were: {0:.0f}\n".format(m.objVal))
        print("{0:.0f} points earned from joining exits:".format(48 - 4 * sum(H[a].x for a in H)))
        #print the clusters left
        for a in G:
            if G[a].x > 0.9:
                print("\tCluster starting at {0} has {1:.0f} exit(s)".format(a, G[a].x))
        #print the points earned from centre squares
        print("{0:.0f} points earned from centre squares".format(sum(X[t,s].x for s in S if Board.is_centre_square(s) for t in T)))
        #print the longest path points and paths
        for e in E:
            print("{0:.0f} points earned from longest {1} with segments".format(sum(D[s,e].x for s in I), "railway" if e == EdgeType.R else "highway"))
            print("\tStart:{0}".format([s for s in I if A[s,e].x > 0.9][0]))
            print("\t{0}".format([s for s in I if D[s,e].x > 0.9 ]))
            
        #print the penalties information
        print("{0:.0f} points from penalties".format(-1* sum(X[t,s].x * t.loose_ends(s) for t in T for s in I) +
                                                      sum(2*Y[s1,s2,e].x for (s1,s2,e) in Y if s1 in I and s2 in I)))
        for s in I:
            score = 0
            score -= sum(t.loose_ends(s) for t in T if X[t,s].x > 0.9)
            score += sum(Y[(s[0]+dr,s[1]+dc),s,e].x for e in E for (dr,dc) in [(-1,0), (0,-1)] if (s[0]+dr,s[1]+dc) in I)
            score += sum(Y[s,(s[0]+dr,s[1]+dc),e].x for e in E for (dr,dc) in [(1,0), (0,1)] if (s[0]+dr,s[1]+dc) in I)
            if score != 0:
                print("\t{0:.0f} penalties at {1}".format(score, s))
        
        print("{0:.0f} points from the bonus point".format(abs(J.x)))
    
if __name__ == "__main__":
    board = rulebook_game()
    s = LastMoveSolver(board, rulebook_moves(board))
    s.solve()

