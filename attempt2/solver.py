
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
        
        #x variables are for whether move m is made at square s
        X = {(t,s) : m.addVar(vtype=GRB.BINARY) for t in T for s in S}
        #y variables for whether there is a link between two adjacent squares with edge type e
        #note that these only go right and down (increasing row/col)
        Y = {(s,(s[0] + dr, s[1] + dc),e) : m.addVar(vtype=GRB.BINARY)
             for s in S for (dr, dc) in [(0,1),(1,0)] for e in [EdgeType.H, EdgeType.R]
             if (s[0] + dr, s[1] + dc) in S}
        
        #constraints
        
        #constraints for if there are connections on any horizontal edges
        horizontal_y_constraints = {(s,e)  :
            m.addConstr(2 * Y[s, (s[0], s[1]+1), e] <= 
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                              quicksum(X[t,(s[0],s[1]+1)] for t in T if t.get_edge_type_on_side(Side.LEFT) == e))
            for s in S if (s[0],s[1]+1) in S for e in [EdgeType.H, EdgeType.R]}
        
        #constraints for if there are connections on any vertical edges
        vertical_y_constraints = {(s,e) :
            m.addConstr(2 * Y[s, (s[0]+1, s[1]), e] <=
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                              quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == e))
            for s in S if (s[0]+1,s[1]) in S for e in [EdgeType.H, EdgeType.R]}
          
        #constraints for clashes on edges joining squares horizontally, preventing railways and highways being connected
        horizontal_clashes = {(s,e) :
            m.addConstr(quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                        quicksum(X[t,(s[0],s[1]+1)] for t in T 
                            if t.get_edge_type_on_side(Side.LEFT) == Side.opposite(e)) <= 1)
            for s in S if (s[0],s[1]+1) in S for e in [EdgeType.H, EdgeType.R]}
            
        #constraints for clashes on edges joining squares vertically, preventing railways & highways connecting
        vertical_clashes = {(s,e) :
            m.addConstr(quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                        quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == Side.opposite(e))
                        <= 1)
            for s in S if (s[0]+1,s[1]) in S for e in [EdgeType.H, EdgeType.R]}
            
            
        #ensure no illegal pieces are placed on start edges
#        no_illegal_start_joins = {}
#        for startR, startC, tile in self._board.get_start_pieces():
#            for startSide in Side:
#                #get the side of the start tile that isn't blank
#                startType = tile.get_edge_type_on_side(startSide)
#                if startType != EdgeType.B:
#                    r, c, side = Board.opposite_edge(startR, startC, startSide)
#                    no_illegal_start_joins[startR, startC] = m.addConstr(
#                            quicksum(X[t, (r,c)] for t in T if t.get_edge_type_on_side(side) == EdgeType.clash_type(startType))
#                            == 0)
                    
            
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
            
        #flow variables can only be set if the connection exists on that edge
        flow_existence = {((r,c),(r+dr,c+dc),e):
            m.addConstr(F[(r,c),(r+dr,c+dc),e] <= (NUM_STARTS * Y[(r,c),(r+dr,c+dc),e]))
            if dr + dc > 0 else
            m.addConstr(F[(r,c),(r+dr,c+dc),e] <= (NUM_STARTS * Y[(r+dr,c+dc),(r,c),e]))
            for r,c in S for (dr,dc) in [(0,1),(0,-1),(1,0),(-1,0)] if (r+dr, c+dc) in S
            for e in [EdgeType.H, EdgeType.R]}
        
            
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
        m.setObjective(quicksum(X[t,s] for s in S if Board.is_centre_square(s) for t in T)  + quicksum(Y[a] for a in Y)
                , GRB.MAXIMIZE)
            
        #optimize
        m.optimize()
        
        self._print_result(m, X, T, S)
    
    """
    print the board with the solution attached
    """
    def _print_result(self, m, X, T, S):
        #find all the pieces and placements that we had and add them to the board
        for t, s in X:
            if X[t,s].x > 0.9 and self._board.is_square_free(s):
                self._board.add_solution_tile(s[0], s[1], t)
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print()
        
        #next print out the resulting score
        print("The total points earned (in this turn) were: {0:.0f}\n".format(m.objVal))
    
    
if __name__ == "__main__":
    board = rulebook_game()
    s = LastMoveSolver(board, rulebook_moves(board))
    s.solve()

