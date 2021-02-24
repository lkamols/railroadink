
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
        S = {(i,j) for i in range(NUM_ROWS) for j in range(NUM_COLS)}
        T = Tile.get_all_variations()
        
        #x variables are for whether move m is made at square s
        X = {(t,s) : m.addVar(vtype=GRB.BINARY) for t in T for s in S}
        #y variables for whether there is a link between two adjacent squares with edge type e
        Y = {(s,(s[0] + dr, s[1] + dc),e) : m.addVar(vtype=GRB.BINARY) for t in T 
             for s in S for (dr, dc) in [(0,1),(1,0)] for e in [EdgeType.H, EdgeType.R]
             if s[0] + dr < NUM_ROWS and s[1] + dc < NUM_COLS}
        
        #constraints
        
        #constraints for if there are connections on any horizontal edges
        horizontal_y_constraints = {(s,e)  :
            m.addConstr(2 * Y[s, (s[0], s[1]+1), e] <= 
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                              quicksum(X[t,(s[0],s[1]+1)] for t in T if t.get_edge_type_on_side(Side.LEFT) == e))
            for s in S if s[1] < NUM_COLS - 1 for e in [EdgeType.H, EdgeType.R]}
        
        #constraints for if there are connections on any vertical edges
        vertical_y_constraints = {(s,e) :
            m.addConstr(2 * Y[s, (s[0]+1, s[1]), e] <=
                              quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                              quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == e))
            for s in S if s[0] < NUM_ROWS - 1 for e in [EdgeType.H, EdgeType.R]}
          
        #constraints for clashes on edges joining squares horizontally, preventing railways and highways being connected
        horizontal_clashes = {(s,e) :
            m.addConstr(quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.RIGHT) == e) +
                        quicksum(X[t,(s[0],s[1]+1)] for t in T 
                            if t.get_edge_type_on_side(Side.LEFT) == Side.opposite(e)) <= 1)
            for s in S if s[0] < NUM_COLS - 1 for e in [EdgeType.H, EdgeType.R]}
            
        #constraints for clashes on edges joining squares vertically, preventing railways & highways connecting
        vertical_clashes = {(s,e) :
            m.addConstr(quicksum(X[t,s] for t in T if t.get_edge_type_on_side(Side.BOTTOM) == e) +
                        quicksum(X[t,(s[0]+1,s[1])] for t in T if t.get_edge_type_on_side(Side.TOP) == Side.opposite(e))
                        <= 1)
            for s in S if s[1] < NUM_ROWS - 1 for e in [EdgeType.H, EdgeType.R]}
            
            
        #ensure no illegal pieces are placed on start edges
        no_illegal_start_joins = {}
        for startR, startC, tile in self._board.get_start_pieces():
            for startSide in Side:
                #get the side of the start tile that isn't blank
                startType = tile.get_edge_type_on_side(startSide)
                if startType != EdgeType.B:
                    r, c, side = Board.opposite_edge(startR, startC, startSide)
                    no_illegal_start_joins[startR, startC] = m.addConstr(
                            quicksum(X[t, (r,c)] for t in T if t.get_edge_type_on_side(side) == EdgeType.clash_type(startType))
                            == 0)
                    
            
        #ensure all the pieces that are part of the board are kept
        default_placements = {s :
            m.addConstr(X[self._board.get_tile_at(s),s] == 1)
            for s in S if not self._board.is_square_free(s)}
            


        #use all of the pieces required to be used
        use_pieces = {p : 
            m.addConstr(quicksum(X[t,s] for s in S if self._board.is_square_free(s)
                                 for t in Tile.get_variations(p)) == 
                        (self._moves[p] if p in self._moves else 0))
            for p in BASIC_PIECES + JUNCTION_PIECES}
            
        #only place one tile in each square
        one_tile_per_square = {s :
            m.addConstr(quicksum(X[t,s] for t in T) <= 1)
            for s in S}
            
            
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
        
        for y in Y:
            if Y[y].x > 0.9:
                print(y)
                
        for x in X:
            if X[x].x > 0.9:
                print(x)
        
        self._print_result(m, X, T, S)
    
    """
    creates all the constraints relating to clashes on internal edges, adds constraints preventing railways and highways
    running into each other
    """
    def _clashes_on_edge_constraints(self, m, T, X, D, internal_edges):
        edge_constraints = {} #constraints preventing pieces being positioned that directly clash with each other
        edge_error_constraints = {} #constraints for the 
        for edge in internal_edges:
            if edge.is_vertical():
                sLeft = (edge.get_row(), edge.get_col() - 1)
                sRight = (edge.get_row(), edge.get_col())
                #there can only be either a highway on the left OR a railway on the right
                edge_constraints[edge, "H"] = m.addConstr(quicksum(X[t,sLeft] for t in T if (t, sLeft) in X and t.get_edge_type_on_side(Side.RIGHT) == EdgeType.H) +
                                quicksum(X[t, sRight] for t in T if (t, sRight) in X and t.get_edge_type_on_side(Side.LEFT) == EdgeType.R) <= 1)
                #similarly there can only be a railway on the left OR a highway on the right
                edge_constraints[edge, "R"] = m.addConstr(quicksum(X[t,sLeft] for t in T if (t, sLeft) in X and t.get_edge_type_on_side(Side.RIGHT) == EdgeType.R) +
                                quicksum(X[t, sRight] for t in T if (t, sRight) in X and t.get_edge_type_on_side(Side.LEFT) == EdgeType.H) <= 1)
                #now for the internal errors constraints
                #something on the left, nothing on the right
                edge_error_constraints[edge, 0] = m.addConstr(quicksum(X[t,sLeft] for t in T if (t, sLeft) in X and t.get_edge_type_on_side(Side.RIGHT) != EdgeType.B) -
                                quicksum(X[t, sRight] for t in T if (t, sRight) in X and t.get_edge_type_on_side(Side.LEFT) != EdgeType.B) <= D[edge, 0])
                #something on the right, nothing on the left
                edge_error_constraints[edge, 1] = m.addConstr(quicksum(X[t, sRight] for t in T if (t, sRight) in X and t.get_edge_type_on_side(Side.LEFT) != EdgeType.B) - 
                                      quicksum(X[t,sLeft] for t in T if (t, sLeft) in X and t.get_edge_type_on_side(Side.RIGHT) != EdgeType.B) <= D[edge, 1])
            else: #horizontal
                sTop = (edge.get_row() - 1, edge.get_col())
                sBottom = (edge.get_row(), edge.get_col())
                #there can only be either a highway on the top OR a railway on the bottom
                edge_constraints[edge, "H"] = m.addConstr(quicksum(X[t,sTop] for t in T if (t, sTop) in X and t.get_edge_type_on_side(Side.BOTTOM) == EdgeType.H) +
                                quicksum(X[t, sBottom] for t in T if (t, sBottom) in X and t.get_edge_type_on_side(Side.TOP) == EdgeType.R) <= 1)
                #similarly, railway top OR highway bottom
                edge_constraints[edge, "H"] = m.addConstr(quicksum(X[t,sTop] for t in T if (t, sTop) in X and t.get_edge_type_on_side(Side.BOTTOM) == EdgeType.R) +
                                quicksum(X[t, sBottom] for t in T if (t, sBottom) in X and t.get_edge_type_on_side(Side.TOP) == EdgeType.H) <= 1)
                #now for the internal errors constraints
                #something on the top, nothing on the bottom
                edge_error_constraints[edge, 0] = m.addConstr(quicksum(X[t,sTop] for t in T if (t, sTop) in X and t.get_edge_type_on_side(Side.BOTTOM) != EdgeType.B) -
                                      quicksum(X[t, sBottom] for t in T if (t, sBottom) in X and t.get_edge_type_on_side(Side.TOP) != EdgeType.B) <= D[edge, 0])
                #something on the bottom, nothing on the top
                edge_error_constraints[edge, 1] = m.addConstr(quicksum(X[t, sBottom] for t in T if (t, sBottom) in X and t.get_edge_type_on_side(Side.TOP) != EdgeType.B) -
                                      quicksum(X[t,sTop] for t in T if (t, sTop) in X and t.get_edge_type_on_side(Side.BOTTOM) != EdgeType.B) <= D[edge, 1])
        return edge_constraints, edge_error_constraints
    
    
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

