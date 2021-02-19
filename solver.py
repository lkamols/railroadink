
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
        m = self._make_model()
        
        m.optimize()
        
        self._print_result(m)
       
    """
    determine if a given placement of a tile at a square clashes with any cluster ends
    returns True if placement is possible and does not clash, False if there is a clash
    """
    def _is_placement_possible(self, tile, square, cluster_ends):
        #create a list of all the edges which could clash with cluster ends
        bad_ends = set()
        for side in Side:
            edgeType = tile.get_edge_type_on_side(side)
            #blanks never clash
            if edgeType != EdgeType.B:
                bad_ends.add((Edge.get_edge_of_piece(square[0], square[1], side), EdgeType.clash_type(edgeType)))
        #then check if any of the bad_ends are in the cluster_ends
        for cluster_end in cluster_ends:
            if cluster_end in bad_ends:
                return False
        #if we made it this far, there were no clashes, and the placement is possible
        return True
                
        
    def _make_model(self):
        m = Model("railroad-ink")
        
        #sets
        S = self._board.get_free_squares()
        T = self._moves.get_all_possible_moves()
        cluster_ends = self._board.get_all_cluster_ends()
        internal_edges = self._board.get_available_internal_edges()
        print(internal_edges)
        
        #x variables are for whether move m is made at square s
        X = {(t,s) : m.addVar(vtype=GRB.INTEGER) for t in T for s in S if self._is_placement_possible(t, s, cluster_ends)}
        self._X = X #just store this to the class to get results from
        
        #constraints
        
        #use all of the pieces required to be used
        use_pieces = {p : 
            m.addConstr(quicksum(X[t,s] for t in self._moves.get_variations(p) for s in S if (t,s) in X) == 
                        self._moves.get_piece_count(p))
            for p in self._moves.get_pieces()}
            
        #only place one tile in each square
        one_tile_per_square = {s :
            m.addConstr(quicksum(X[t,s] for t in T if (t,s) in X) <= 1)
            for s in S}
            
        return m
    
    
    def _print_result(self, m):
        #find all the pieces and placements that we had and add them to the board
        for t, s in self._X:
            if self._X[t,s].x > 0.9:
                self._board.add_solution_tile(s[0], s[1], t)
        self._board.fancy_board_print()
    
    
if __name__ == "__main__":
    board = rulebook_game()
    s = LastMoveSolver(board, rulebook_moves(board))
    s.solve()