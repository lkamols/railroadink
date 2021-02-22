
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
        S = self._board.get_free_squares()
        T = self._moves.get_all_possible_moves()
        cluster_ends = self._board.get_all_cluster_ends()
        internal_edges = self._board.get_available_internal_edges()
        C, paths = self._board.get_cluster_paths()
        print(internal_edges)
        
        #x variables are for whether move m is made at square s
        X = {(t,s) : m.addVar(vtype=GRB.BINARY) for t in T for s in S if self._is_placement_possible(t, s, cluster_ends)}
        #d variables are for errors on internal edges
        D = {(e,c) : m.addVar(vtype=GRB.BINARY) for e in internal_edges for c in range(2)}
        
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
            
        edge_constraints, edge_error_constraints = self._clashes_on_edge_constraints(m, T, X, D, internal_edges) 
        
        #add constraints and variables for the paths joining clusters together and whether clusters are being joined together
        YC, YP, path_constraints, join_constraints = self._cluster_path_constraints(m, C, paths, T, S, X)
        
        #set a constraint so that two clusters can only be joined IFF there isn't a previous cluster which joins
        #to both of them, prevents a join of (a,b,c) counted 3 times as a-b a-c and b-c
        single_join_constraints = {(other_id, start_id, finish_id) :
            m.addConstr(YC[start_id, finish_id] <= 2 - YC[other_id, start_id] - YC[other_id, finish_id])
            for other_id in C for start_id in C for finish_id in C 
            if other_id < start_id and start_id < finish_id and 
            (other_id, start_id) in YC and (other_id, finish_id) in YC and (start_id, finish_id) in YC}
        
            
        #set the objective function
        m.setObjective(quicksum(4 *YC[a] for a in YC) #cluster joins
                        + quicksum(X[t,s] for s in S if Board.is_centre_square(s) for t in T if (t,s) in X) #centre square uses
                        + quicksum(X[t,s] * self._board.placement_score(s, t) for t in T for s in S if (t,s) in X) #static error count
                        - quicksum(D[a] for a in D) #internal error count
                , GRB.MAXIMIZE)
    
            
        #optimize
        m.optimize()
        
        self._print_result(m, X, D, YC, YP, T, S)
       
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
    creates all the contraints for the cluster paths
    """
    def _cluster_path_constraints(self, m, C, paths, T, S, X):
        YC = {} #variables for the joining of clusters together
        YP = {} #variables for paths being 
        path_constraints = {}
        join_constraints = {}
        for start_id in C:
            for finish_id in C:
                #only have the start_id less than the finish_id to keep things one directional
                if start_id < finish_id:
                    joining_paths = paths.get((start_id, finish_id), [])
                    if len(joining_paths) > 0:
                        YC[start_id, finish_id] = m.addVar(vtype=GRB.BINARY)
                        for count, path in enumerate(joining_paths):
                            YP[start_id, finish_id, count] = m.addVar(vtype=GRB.BINARY)
                            #the colossus of all constraints, if this path exists in the board, then allow this variable to be 1
                            #since we have the constraint that only one piece can go in each square, this can just be done by ensuring
                            #one valid piece is placed at each step along the way
                            #need to ensure we aren't turning a corner with an overpass though
                            path_constraints[start_id, finish_id, count] = \
                                    m.addConstr(quicksum(X[t,(path[i][0], path[i][1])] for i in range(1, len(path)) for t in T
                                                           if (t, (path[i][0], path[i][1])) in X 
                                                           and t.get_edge_type_on_side(path[i][2]) != EdgeType.B
                                                           and t.get_edge_type_on_side(Side.opposite(path[i-1][2])) != EdgeType.B
                                                           and not (t.get_piece() == Piece.OVERPASS and path[i][2] != path[i-1][2])) >=
                                                (len(path) - 1) * YP[start_id, finish_id, count])

                        #then if any of these paths variables are 1, the variable for joining the two clusters together can be made 1
                        join_constraints[start_id, finish_id] = m.addConstr(YC[start_id, finish_id] <= 
                                                quicksum(YP[start_id, finish_id, count] for count in range(len(joining_paths))))    
        return YC, YP, path_constraints, join_constraints
    
    
    """
    print the board with the solution attached
    """
    def _print_result(self, m, X, D, YC, YP, T, S):
        #find all the pieces and placements that we had and add them to the board
        for t, s in X:
            if X[t,s].x > 0.9:
                self._board.add_solution_tile(s[0], s[1], t)
        #then do a super fancy board print showing the exact solution
        self._board.fancy_board_print()
        
        #next print out the resulting score
        print("The total points earned (in this turn) were: {0:.0f}\n".format(m.objVal))
        
        #print out the information about the clusters which were joined together
        print("{0:.0f} point(s) were earned from joining cluster, the clusters joined were:".format( 4 * sum(YC[a].x for a in YC)))
        for start_id, finish_id in YC:
            if YC[start_id, finish_id].x > 0.9:
                start_row, start_col = Cluster.recover_from_identifier(start_id)
                end_row, end_col = Cluster.recover_from_identifier(finish_id)
                print("\t({0},{1}) - ({2},{3})".format(start_row, start_col, end_row, end_col))
          
        #print information about the centre squares
        print("{0:.0f} point(s) were earned from centre squares:".format(
                sum(X[t,s].x for s in S if Board.is_centre_square(s) for t in T if (t,s) in X )))
        print("\t",[s for s in S if Board.is_centre_square(s) for t in T if (t,s) in X and X[t,s].x > 0.9])
        
        print("{0:.0f} point(s) attributed to static errors".format( 
              sum(X[t,s].x * self._board.placement_score(s, t) for t in T for s in S if (t,s) in X)))
        for t in T:
            for s in S:
                if (t,s) in X and X[t,s].x > 0.9:
                    print("\t",self._board.placement_score(s, t), "point(s) at", s)
                    
        print("-{0:.0f} point(s) attributed to internal errors".format(
                sum(D[a].x for a in D)))
        for edge, c in D:
            if (D[edge,c].x > 0.9):
                print("\t{0}".format(edge))
    
    
if __name__ == "__main__":
    board = rulebook_game()
    s = LastMoveSolver(board, rulebook_moves(board))
    s.solve()