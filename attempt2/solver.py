
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
        
        #sets
        I = {(i,j) for i in range(NUM_ROWS) for j in range(NUM_COLS)}
        O = Board.get_start_squares()
        S = I.union(O)
        T = Tile.get_all_variations()
        E = [EdgeType.H, EdgeType.R]
        
        #x variables are for whether move m is made at square s
        X = {(t,s) : m.addVar(vtype=GRB.BINARY) for t in T for s in S}
        #y variables for whether there is a link between two adjacent squares with edge type e
        #note that these only go right and down (increasing row/col)
        Y = {((r,c),(r+dr,c+dc),e) : m.addVar(vtype=GRB.BINARY)
             for (r,c) in S for (dr, dc) in [(0,1),(1,0)] for e in E
             if (r + dr, c + dc) in S}
        F = {((r,c),(r+dr,c+dc),e): m.addVar() for r,c in S 
                for (dr,dc) in [(0,1),(0,-1),(1,0),(-1,0)] if (r+dr,c+dc) in S for e in E}
        FF = {(s,e) : m.addVar() for s in I for e in E} #transfer flow between rails and highways at square s (from e)
        G = {s : m.addVar() for s in O}
        H = {s : m.addVar(vtype=GRB.BINARY) for s in O}
        
        #constraints
        
        #constraints for if there are connections on any horizontal edges
        horizontal_y_constraints = {(s,e)  :
            m.addConstr(2 * Y[s, (s[0], s[1]+1), e] <= 
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                              quicksum(X[t,(s[0],s[1]+1)] for t in T if t.get_edge_type_on_side(Side.LEFT) == e))
            for s in S if (s[0],s[1]+1) in S for e in E}
        
        #constraints for if there are connections on any vertical edges
        vertical_y_constraints = {(s,e) :
            m.addConstr(2 * Y[s, (s[0]+1, s[1]), e] <=
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                              quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == e))
            for s in S if (s[0]+1,s[1]) in S for e in E}
          
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
            
        #only place one tile in each square
        one_tile_per_square = {s :
            m.addConstr(quicksum(X[t,s] for t in T) <= 1)
            for s in S}
            
        #the flow into an internal square must be the same as the flow out
        internal_flows = {(s,e) :
            m.addConstr(quicksum(F[s,ss,e] for ss in self._board.adjacents(s)) + FF[s,EdgeType.clash_type(e)] ==
                        quicksum(F[ss,s,e] for ss in self._board.adjacents(s)) + FF[s,e])
            for s in I for e in E}
            
        external_flows = {s :
            m.addConstr(1 + quicksum(F[ss,s,e] for ss in self._board.adjacents(s) for e in E) ==
                        quicksum(F[s,ss,e] for ss in self._board.adjacents(s) for e in E) + G[s])
            for s in O}
            
        sink_connections = {s : 
            m.addConstr(G[s] <= NUM_STARTS * H[s])
            for s in O}
            
        #flow variables can only be set if the connection exists on that edge
        flow_existence = {((r,c),(r+dr,c+dc),e):
            m.addConstr(F[(r,c),(r+dr,c+dc),e] <= (NUM_STARTS * Y[(r,c),(r+dr,c+dc),e]))
            if dr + dc > 0 else
            m.addConstr(F[(r,c),(r+dr,c+dc),e] <= (NUM_STARTS * Y[(r+dr,c+dc),(r,c),e]))
            for r,c in S for (dr,dc) in [(0,1),(0,-1),(1,0),(-1,0)] if (r+dr, c+dc) in S for e in E}
            
        #transfer flow existence, if the piece played is a junction, we can flow between highways and railways on that square
        transfer_flow = {(s,e):
            m.addConstr(FF[s,e] <= NUM_STARTS * quicksum(X[t,s] for t in T if t.get_piece() in SWITCH_PIECES))
            for s in I for e in E}
        
            
        #play special pieces at most once each
        special_once = {p:
                m.addConstr(quicksum(X[t,s] for s in S if self._board.is_square_free(s) for t in Tile.get_variations(p))<=1)
                for p in SPECIAL_PIECES}
            
        #play at most one special piece this turn  
        m.addConstr(quicksum(X[t,s] for s in S if self._board.is_square_free(s)
                     for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=1)

        #play max 3 special pieces total
        m.addConstr(quicksum(X[t,s] for s in S
                     for p in SPECIAL_PIECES for t in Tile.get_variations(p))<=3)
            
        #set the objective function
        m.setObjective(quicksum(X[t,s] for s in S if Board.is_centre_square(s) for t in T) +48 - 4 * quicksum(H[a] for a in H)
                , GRB.MAXIMIZE)
            
        #optimize
        m.optimize()

        self._print_result(m, X, G, H, T, S)
 
    """
    print the board with the solution attached
    """
    def _print_result(self, m, X, G, H, T, S):
        #find all the pieces and placements that we had and add them to the board
        for t, s in X:
            if X[t,s].x > 0.9 and self._board.is_square_free(s):
                self._board.add_solution_tile(s[0], s[1], t)
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print()
        
        #next print out the resulting score
        print("The total points earned (in this turn) were: {0:.0f}\n".format(m.objVal))
        print("{0:.0f} points earned from joining exits:".format(48 - 4 * sum(H[a].x for a in H)))
        #print the clusters left
        for a in G:
            if G[a].x > 0.9:
                print("\tCluster starting at {0} has {1:.0f} exit(s)".format(a, G[a].x))
        #print the points earned from centre squares
        print("{0:.0f} points earned from centre squares".format(sum(X[t,s].x for s in S if Board.is_centre_square(s) for t in T)))
    
if __name__ == "__main__":
    board = rulebook_game()
    s = LastMoveSolver(board, rulebook_moves(board))
    s.solve()

