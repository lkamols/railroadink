from enum import Enum
from dataclasses import dataclass
from PIL import Image

NUM_ROWS = 7
NUM_COLS = 7

#photo measurements to get the positioning correct
TOP_OFFSET = 44
LEFT_OFFSET = 30
BOARD_WIDTH = 669
BOARD_HEIGHT = 669

PHOTOS_FOLDER = "Railroad-Pictures/"

"""
Enum for the types of edges that can be on a piece
"""
class Edge(Enum):
    R = 0 #railway
    H = 1 #highway
    B = 2 #blank
   
"""
All the different possible pieces
"""
class Piece(Enum):
    #basic pieces
    RAILWAY_CORNER = 0
    RAILWAY_T = 1
    RAILWAY_STRAIGHT = 2
    HIGHWAY_CORNER = 3
    HIGHWAY_T = 4
    HIGHWAY_STRAIGHT = 5
    #junction pieces
    OVERPASS = 6
    STRAIGHT_STATION = 7
    CORNER_STATION = 8
    #special pieces
    THREE_H_JUNCTION = 9
    THREE_R_JUNCTION = 10
    HIGHWAY_JUNCTION = 11
    RAILWAY_JUNCTION = 12
    CORNER_JUNCTION = 13
    CROSS_JUNCTION = 14
    #start pieces (the edge tiles)
    START_RAILWAY = 15
    START_HIGHWAY = 16
    #the magical blank tile
    BLANK = 17
    #the overpass tile will get split into two separate tiles sometimes
    OVERPASS_RAILWAY = 18
    OVERPASS_HIGHWAY = 19
    
#grouping of pieces
BASIC_PIECES = [Piece.RAILWAY_CORNER, Piece.RAILWAY_T, Piece.RAILWAY_STRAIGHT,
                Piece.HIGHWAY_CORNER, Piece.HIGHWAY_T, Piece.HIGHWAY_STRAIGHT]
JUNCTION_PIECES = [Piece.OVERPASS, Piece.STRAIGHT_STATION, Piece.CORNER_STATION]
SPECIAL_PIECES = [Piece.THREE_H_JUNCTION, Piece.THREE_R_JUNCTION, Piece.HIGHWAY_JUNCTION,
                  Piece.RAILWAY_JUNCTION, Piece.CORNER_JUNCTION, Piece.CROSS_JUNCTION]
START_PIECES = [Piece.START_RAILWAY, Piece.START_HIGHWAY]
OVERPASS_SEGMENTS = [Piece.OVERPASS_RAILWAY, Piece.OVERPASS_HIGHWAY]

"""
The different possible Rotations of a piece
"""
class Rotation(Enum):
    I = 0 #identity
    #turns considered clockwise
    R90 = 1
    R180 = 2
    R270 = 3
   
"""
The sides of a piece
"""
class Side(Enum):
    TOP = 0
    RIGHT = 1
    BOTTOM = 2
    LEFT = 3
    
    """
    get the side opposite of the provided side
    """
    @staticmethod
    def opposite(side):
        if side == Side.TOP:
            return Side.BOTTOM
        elif side == Side.BOTTOM:
            return Side.TOP
        elif side == Side.RIGHT:
            return Side.LEFT
        else:
            return Side.RIGHT

"""
basically just a struct object for storing one edge of a cluster
"""
@dataclass 
class ClusterEdge:
    row: int
    col: int
    side: Side
    edge: Edge
    
    
#start locations of all the highways and railways
HIGHWAY_START_POSITIONS = [(-1, 1, Rotation.R180), (-1, 5, Rotation.R180),
                           (3, -1, Rotation.R90), (3, NUM_COLS, Rotation.R270),
                           (NUM_ROWS, 1, Rotation.I), (NUM_ROWS, 5, Rotation.I)]
RAILWAY_START_POSITIONS = [(-1, 3, Rotation.R180), (NUM_ROWS, 3, Rotation.I),
                           (1, -1, Rotation.R90), (5, -1, Rotation.R90),
                           (1, NUM_COLS, Rotation.R270), (5, NUM_COLS, Rotation.R270)]

"""
Class for one tile, does not contain its positional information
"""
class Tile:
    
    #map of all the tiles in their default rotation
    _tile_map = {
        Piece.RAILWAY_CORNER: (Edge.R, Edge.B, Edge.B, Edge.R),
        Piece.RAILWAY_T: (Edge.R, Edge.R, Edge.B, Edge.R),
        Piece.RAILWAY_STRAIGHT: (Edge.R, Edge.B, Edge.R, Edge.B),
        Piece.HIGHWAY_CORNER: (Edge.H, Edge.B, Edge.B, Edge.H),
        Piece.HIGHWAY_T: (Edge.H, Edge.H, Edge.B, Edge.H),
        Piece.HIGHWAY_STRAIGHT: (Edge.H, Edge.B, Edge.H, Edge.B),
        Piece.OVERPASS: (Edge.H, Edge.R, Edge.H, Edge.R),
        Piece.STRAIGHT_STATION: (Edge.R, Edge.B, Edge.H, Edge.B),
        Piece.CORNER_STATION: (Edge.R, Edge.B, Edge.B, Edge.H),
        Piece.THREE_H_JUNCTION: (Edge.H, Edge.H, Edge.R, Edge.H),
        Piece.THREE_R_JUNCTION: (Edge.H, Edge.R, Edge.R, Edge.R),
        Piece.HIGHWAY_JUNCTION: (Edge.H, Edge.H, Edge.H, Edge.H),
        Piece.RAILWAY_JUNCTION: (Edge.R, Edge.R, Edge.R, Edge.R),
        Piece.CORNER_JUNCTION: (Edge.H, Edge.R, Edge.R, Edge.H),
        Piece.CROSS_JUNCTION: (Edge.H, Edge.R, Edge.H, Edge.R),  
        Piece.START_RAILWAY: (Edge.R, Edge.B, Edge.B, Edge.B),
        Piece.START_HIGHWAY: (Edge.H, Edge.B, Edge.B, Edge.B),
        Piece.BLANK: (Edge.B, Edge.B, Edge.B, Edge.B),
        Piece.OVERPASS_RAILWAY: (Edge.B, Edge.R, Edge.B, Edge.R),
        Piece.OVERPASS_HIGHWAY: (Edge.H, Edge.B, Edge.H, Edge.B)
        }
    
    _tile_pics = {
        Piece.RAILWAY_CORNER: "railway-corner.png",
        Piece.RAILWAY_T: "railway-t.png",
        Piece.RAILWAY_STRAIGHT: "railway-straight.png",
        Piece.HIGHWAY_CORNER: "highway-corner.png",
        Piece.HIGHWAY_T: "highway-t.png",
        Piece.HIGHWAY_STRAIGHT: "highway-straight.png",
        Piece.OVERPASS: "overpass.png",
        Piece.STRAIGHT_STATION: "straight-station.png",
        (Piece.CORNER_STATION, False): "corner-station.png",
        (Piece.CORNER_STATION, True): "corner-station-flipped.png",
        Piece.THREE_H_JUNCTION: "three-h-junction.png",
        Piece.THREE_R_JUNCTION: "three-r-junction.png",
        Piece.HIGHWAY_JUNCTION: "highway-junction.png",
        Piece.RAILWAY_JUNCTION: "railway-junction.png",
        Piece.CORNER_JUNCTION: "corner-junction.png",
        Piece.CROSS_JUNCTION: "cross-junction.png",             
    }
    
    """
    Constructor, given a piece and a rotation
    """
    def __init__(self, piece, rotation, flip=False):
        self._piece = piece
        self._rotation = rotation
        self._flip = flip
        #load in all the left, right, down, up and overpass values
        #load these upon creation because they will be accessed multiple times
        self._dirs = {}
        self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM], self._dirs[Side.LEFT] = self._tile_map[piece]
        #flips occur before rotations
        if flip:
            self._reverse()
        self._rotate(rotation)
        
    """
    rotate the tile by the given transformation
    """
    def _rotate(self, rotation):
        #rotate by the given transfrom, enum values are the number of rotations required
        for rotations in range(rotation.value):
            #change all the assignments in the same line, handles the required temporary variables
            self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM], self._dirs[Side.LEFT] = \
                    self._dirs[Side.LEFT], self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM]
     
    """
    flip the piece, this flips it along the top-left to bottom-right diagonal.
    why this axis? because it only is required for the corner-station piece, and this flips the railway and highway
    """               
    def _reverse(self):
        self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM], self._dirs[Side.LEFT] = \
                self._dirs[Side.LEFT], self._dirs[Side.BOTTOM], self._dirs[Side.RIGHT], self._dirs[Side.TOP]
         
    """
    get the image associated with this piece and rotation, scaled to fit on the board image
    """
    def get_image(self):
        #get the correct image
        if self._piece == Piece.CORNER_STATION:
            piece_image = Image.open(PHOTOS_FOLDER + self._tile_pics[(self._piece, self._flip)])
        else:
            piece_image = Image.open(PHOTOS_FOLDER + self._tile_pics[self._piece])
        #resize the image
        piece_image = piece_image.resize([BOARD_WIDTH//NUM_COLS, BOARD_HEIGHT//NUM_ROWS], Image.ANTIALIAS)
        #rotate the image, note that this library does counter clockwise rotations, and we encode in clockwise
        #so the rotation amounts are inverses
        if self._rotation == Rotation.R90:
            piece_image = piece_image.rotate(270)
        elif self._rotation == Rotation.R180:
            piece_image = piece_image.rotate(180)
        elif self._rotation == Rotation.R270:
            piece_image = piece_image.rotate(90)
        return piece_image
    
    """
    get the edge type associated with one of the directions
    """
    def get_edge_type_on_side(self, side):
        return self._dirs[side]
    
    #GETTERS
    
    def get_piece(self):
        return self._piece
    
    def get_rotation(self):
        return self._rotation
    
    def get_overpass(self):
        return self._piece == Piece.OVERPASS
    
    """
    override the equality function to treat two Tiles with the same value the same
    """
    def __eq__(self, obj):
        if not isinstance(obj, Tile):
            return False
        else:
            return (self.piece == obj.piece and self._rotation == obj._rotation and self._flip == obj._flip)
    
    """
    override the representation function so printing is readable
    """
    def __repr__(self):
        return "({0},{1},{2},{3},{4},{5})".format(self._piece.name, self._rotation.name, 
               self._dirs[Side.TOP].name, self._dirs[Side.RIGHT].name, self._dirs[Side.BOTTOM].name,
               self._dirs[Side.LEFT].name)
 
"""
A class for all the information about a given state of play
"""
class Board:
    
    """
    Constructor.
    Creates an empty board with no tiles in it
    """
    def __init__(self):
        #create an empty board with no tiles in it yet
        self._board = [[Tile(Piece.BLANK, Rotation.I)]*NUM_COLS for i in range(NUM_ROWS)]
        self._initialise_start_tiles()
        self._special_routes = [] #the special routes that have been used
      
    """
    add a tile to the board
    """
    def add_tile(self, row, col, piece, rotation, flip=False):
        self._board[row][col] = Tile(piece, rotation, flip)
        if piece in SPECIAL_PIECES:
            self._special_routes += [piece]
        
    """
    add a start tile to the board, these are the pieces around the edge
    """
    def _add_start_tile(self, row, col, piece, rotation):
        self._start_tiles += [(row, col, Tile(piece, rotation))]
        
    """
    initialise all the start pieces
    """
    def _initialise_start_tiles(self):
        self._start_tiles = []
        for row, col, rotation in RAILWAY_START_POSITIONS:
            self._add_start_tile(row, col, Piece.START_RAILWAY, rotation)
        for row, col, rotation in HIGHWAY_START_POSITIONS:
            self._add_start_tile(row, col, Piece.START_HIGHWAY, rotation)
        
    """
    creates an image corresponding to the board,
    file - the location to store the new image, if the file is None, displays it
    """
    def fancy_board_print(self, file=None):
        #create a new image with the board in the background
        board = Image.open(PHOTOS_FOLDER + "board.png")
        im = Image.new('RGB', board.size)
        im.paste(board, (0,0))
        #then go through each of the tiles and add them
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                if self._board[row][col].get_piece() != Piece.BLANK:
                    piece_image = self._board[row][col].get_image()
                    im.paste(piece_image, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS, TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS))
        
        #now display the image, depending on if a file is given
        if file == None:
            im.show()
        else:
            im.save(file)
            
    """
    create a cluster for each of the squares on the board
    """       
    def _initialise_clusters(self):
        clusters = []
        #iterate through each of the rows and cols and create a new cluster at each square
        for row in range(NUM_ROWS):
            row_clusters = []
            for col in range(NUM_COLS):
                tile = self._board[row][col]
                #if the piece is an overpass, treat it as two separate tiles for clustering
                if tile.get_piece() == Piece.OVERPASS:
                    railway_tile = Tile(Piece.OVERPASS_RAILWAY, tile.get_rotation())
                    highway_tile = Tile(Piece.OVERPASS_HIGHWAY, tile.get_rotation())
                    row_clusters += [[Cluster(row, col, railway_tile), Cluster(row, col, highway_tile)]]
                else:
                    row_clusters += [[Cluster(row, col, tile)]] #this is a list of clusters to handle overpasses
            clusters += [row_clusters]
        return clusters
    
    """
    process all of the start clusters by trying to join them with any adjacent pieces
    """
    def _process_start_clusters(self, start_clusters, other_clusters):
        for start_cluster in start_clusters:
            if start_cluster.get_row() == -1: #these are the top clusters
                #this is a for loop for overpasses, usually only one element in the list
                for other_cluster in other_clusters[start_cluster.get_row() + 1][start_cluster.get_col()]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.BOTTOM)
            elif start_cluster.get_row() == NUM_ROWS: #these are the ones on the bottom
                for other_cluster in other_clusters[start_cluster.get_row() - 1][start_cluster.get_col()]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.TOP)
            elif start_cluster.get_col() == -1: #the ones on the left
                for other_cluster in other_clusters[start_cluster.get_row()][start_cluster.get_col() + 1]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.RIGHT)
            elif start_cluster.get_col() == NUM_COLS: #on the right
                for other_cluster in other_clusters[start_cluster.get_row()][start_cluster.get_col() - 1]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.LEFT)
      
    """
    process all non-start clusters by joining them together where there are connections
    """              
    def _process_other_clusters(self, clusters):
        #only reach up and left, this means that every bridge will be processed once
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                #try and join with the cluster above - unless we are in the top row
                if row != 0:
                    #need to go through this list, there is almost certainly only one element - unless it's an overpass
                    for cluster in clusters[row][col]:
                        for cluster_above in clusters[row - 1][col]:
                            Cluster.try_join_clusters(cluster, cluster_above, Side.TOP)
                #try and join with the cluster to the left - unless we are in the left column
                if col != 0:
                    for cluster in clusters[row][col]:
                        for cluster_left in clusters[row][col - 1]:
                            Cluster.try_join_clusters(cluster, cluster_left, Side.LEFT)
     
    """
    get all the representative elements in the clusters. These are the top of each cluster
    and contain all information about the cluster
    """                       
    def _get_cluster_representatives(self, start_clusters, clusters):
        cluster_reps = []
        for cluster in start_clusters:
            if cluster.is_representative():
                cluster_reps += [cluster]
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                for cluster in clusters[row][col]:
                    if cluster.is_representative():
                        cluster_reps += [cluster]
        return cluster_reps
    
    """
    check for any illegal clusters that are detached from any start point, these are illegal
    raises ValueError for any illegal board configurations
    """
    def _check_for_illegal_clusters(self, cluster_reps):
        for cluster in cluster_reps:
            if not cluster.is_blank_cluster() and cluster.get_start_count() == 0:
                raise ValueError("Cluster has no start element -", cluster.get_cluster_tiles())
        
       
    """
    find all the clusters in the board, returns a list of clusters
    """
    def find_clusters(self):
        #first create clusters for all of the start tiles and all the tiles on the board
        start_clusters = []
        for row, col, tile in self._start_tiles:
            start_clusters += [Cluster(row, col, tile)]
        #then create clusters for all of the actual tiles
        clusters = self._initialise_clusters()
        
        self._process_start_clusters(start_clusters, clusters)
                    
        self._process_other_clusters(clusters)
        #next process all the other clusters, only reach up and left, since each pair only needs to be done once

        #find all the representative elements of the clusters, these have parents that have themselves as parents
        cluster_reps = self._get_cluster_representatives(start_clusters, clusters)
        
        #do a little check to ensure there aren't any non-blank clusters that aren't attached to an edge
        self._check_for_illegal_clusters(cluster_reps)
        return cluster_reps
     
    #GETTER METHODS
                                        
    def get_used_special_routes(self):
        return self._special_routes
        
    def get_piece_at(self, row, col):
        return self._board[row][col]

   
"""
A cluster of adjoining pieces in the form of a disjoint set, 
stores all the information about the cluster in the top level element in the disjoint set
"""
class Cluster:
    
    """
    initialise a cluster with just one tile at the given location
    """
    def __init__(self, row, col, tile):
        self._rank = 1 #the max height of the disjoint cluster set
        self._parent = self
        self._tile = tile
        self._row = row
        self._col = col
        self._blank_cluster = (tile.get_piece() == Piece.BLANK) #whether this cluster is a blank cluster or a tiled cluster
        self._cluster_tiles = [(row, col, tile)]
        
        #initialise the count of start pieces
        if tile.get_piece() in START_PIECES:
            self._start_count = 1
        else:
            self._start_count = 0
        
        #add all the edges of the cluster
        self._frontier = []
        if not self._blank_cluster:
            for side in Side:
                edge = tile.get_edge_type_on_side(side)
                if edge != Edge.B:
                    self._frontier += [ClusterEdge(row, col, side, edge)]

    """
    find the representative element of the disjoint set containing this tile cluster
    applies the path compression heuristic
    """     
    def find_set(self):
        if self._parent != self:
            self._parent = self._parent.find_set()
        return self._parent
    
    """
    find an element of the frontier corresponding to the given row, column and side
    """
    def _find_in_frontier(self, row, col, side):       
        for ce in self._frontier:
            if ce.row == row and ce.col == col and ce.side == side:
                return ce
        raise ValueError("{0}, {1}, {2} not found in frontier".format(row, col, side.name))
        
    """
    remove an element from the frontier
    """
    def _remove_from_frontier(self, ce):
        self._frontier.remove(ce)
            
        
    """
    actually merge two clusters together given their representative elements
    """
    @staticmethod
    def _join_clusters(representative1, representative2):
        #do this with the union by rank heuristic to ensure the clusters keep depth low
        if representative1._rank > representative2._rank:
            representative2._parent = representative1 #point cluster 2 to cluster 1
            #merge the frontier and cluster tiles list together so that rep 1 has all the joined information
            representative1._frontier += representative2._frontier
            representative1._cluster_tiles += representative2._cluster_tiles
            representative1._start_count += representative2._start_count
        else:
            representative1._parent = representative2
            representative2._frontier += representative1._frontier
            representative2._cluster_tiles += representative1._cluster_tiles
            representative2._start_count += representative1._start_count
            #increase the rank if they were the same
            if representative1._rank == representative2._rank:
                representative2._rank += 1 

        
    """
    join the clusters that tile1 and tile2 are in (not necessarily representative elements)
    side - the side of tile1 that tile2 is supposed to be on, this function assumes that the given tiles are adjacent
    returns False if the two entered broke the game rules
    """
    @staticmethod
    def try_join_clusters(tile1, tile2, side):
        #get the representative element of each of the tiles
        representative1 = tile1.find_set()
        representative2 = tile2.find_set()
        
        #determine whether each of these pieces is an overpass, there are some overpass edge cases
        isOverpass1 = tile1._tile.get_piece() in OVERPASS_SEGMENTS
        isOverpass2 = tile2._tile.get_piece() in OVERPASS_SEGMENTS
        
        #if they are already in the same cluster, don't join them again
        #THIS MAY NEED TO BE MOVED, MIGHT NEED TO REMOVE THE ELEMENTS FROM THE FRONTIER STILL
        if representative1 == representative2:
            return
        
        #get the edge types out because they will be used a lot and are long
        edge1 = tile1._tile.get_edge_type_on_side(side)
        edge2 = tile2._tile.get_edge_type_on_side(Side.opposite(side))
        
        #now find the element of the frontier of each of them
        #there is only an element on the frontier if it's not a blank edge
        #these may not be defined, but they aren't used unless they are defined
        #there is an edge case when processing overpasses that this edge may have been added to another cluster
        #and removed from consideration, there is a check for that edge case as well
        if edge1 != Edge.B and not (isOverpass2 and edge2 == Edge.B):
            frontierEdge1 = representative1._find_in_frontier(tile1._row, tile1._col, side)
        if edge2 != Edge.B and not (isOverpass1 and edge1 == Edge.B):
            frontierEdge2 = representative2._find_in_frontier(tile2._row, tile2._col, Side.opposite(side))
        
        #consider the cases with two blank clusters, they will get joined together
        if representative1._blank_cluster and representative2._blank_cluster:
            #if both clusters are blank clusters, join them together
            Cluster._join_clusters(representative1, representative2)
        #check for if there is one blank cluster and the other isn't
        elif representative1._blank_cluster and not representative2._blank_cluster:
            #if there is an edge leading into the blank cluster though, add it
            #this allows us to detect detached squares
            if edge2 != Edge.B:
                representative1._frontier += [frontierEdge2]
        elif representative2._blank_cluster and not representative1._blank_cluster:
            if edge1 != Edge.B:
                representative2._frontier += [frontierEdge1]
        #at this point in the chain, they are both not blank clusters
        #if they are the same we will be joining the clusters together, remove the edges that joined them together
        elif (edge1 == Edge.H and edge2 == Edge.H) or (edge1 == Edge.R and edge2 == Edge.R):
            representative1._remove_from_frontier(frontierEdge1)
            representative2._remove_from_frontier(frontierEdge2)
            Cluster._join_clusters(representative1, representative2)
        #if they have clashes, then this is a problem and raise an error to say that this board is invalid
        elif (edge1 == Edge.H and edge2 == Edge.R) or (edge1 == Edge.R and edge2 == Edge.H):
            raise ValueError("board invalid - clash between ({0},{1}) and ({2},{3})".format(
                    tile1._row, tile1._col, tile2._row, tile2._col))
        #if we have a non-blank running into a blank (but neither are blank clusters), remove the side running into the
        #blank from the cluster, because we won't ever be able to join to it, this is a -1 point, but we are only
        #interested in point changes
        #don't do this for overpass segments, because there is 'another' tile there
        elif edge1 == Edge.B and not isOverpass1 and edge2 != Edge.B:
            representative2._remove_from_frontier(frontierEdge2)
        elif edge2 == Edge.B and not isOverpass2 and edge1 != Edge.B:
            representative1._remove_from_frontier(frontierEdge1)
            
            
    #GETTER METHODS
    
    def get_row(self):
        return self._row
    
    def get_col(self):
        return self._col
    
    def get_parent(self):
        return self._parent
    
    def is_representative(self):
        return self._parent == self
    
    def is_blank_cluster(self):
        return self._blank_cluster
    
    def get_cluster_tiles(self):
        return self._cluster_tiles
        
    def get_frontier(self):
        return self._frontier
    
    def get_start_count(self):
        return self._start_count
        

"""
create the board for the game shown in the rulebook
"""
def rulebook_game():
    board = Board()
    board.add_tile(0, 1, Piece.HIGHWAY_STRAIGHT, Rotation.I)
    board.add_tile(1, 0, Piece.RAILWAY_STRAIGHT, Rotation.R90)
    board.add_tile(1, 1, Piece.OVERPASS, Rotation.I)
    board.add_tile(1, 2, Piece.RAILWAY_STRAIGHT, Rotation.R90)
    board.add_tile(1, 3, Piece.THREE_R_JUNCTION, Rotation.R180)
    board.add_tile(1, 4, Piece.CORNER_STATION, Rotation.I, flip=True)
    board.add_tile(2, 1, Piece.HIGHWAY_STRAIGHT, Rotation.I)
    board.add_tile(2, 3, Piece.HIGHWAY_CORNER, Rotation.R90)
    board.add_tile(2, 5, Piece.HIGHWAY_CORNER, Rotation.R270)
    board.add_tile(3, 0, Piece.HIGHWAY_STRAIGHT, Rotation.R90)
    board.add_tile(3, 1, Piece.HIGHWAY_T, Rotation.I)
    board.add_tile(3, 2, Piece.HIGHWAY_CORNER, Rotation.R270)
    board.add_tile(3, 5, Piece.HIGHWAY_T, Rotation.R90)
    board.add_tile(3, 6, Piece.HIGHWAY_STRAIGHT, Rotation.R90)
    board.add_tile(4, 2, Piece.HIGHWAY_STRAIGHT, Rotation.I)
    board.add_tile(4, 3, Piece.CORNER_STATION, Rotation.R180, flip=False)
    board.add_tile(4, 4, Piece.HIGHWAY_JUNCTION, Rotation.I)
    board.add_tile(5, 0, Piece.RAILWAY_STRAIGHT, Rotation.R90)
    board.add_tile(5, 1, Piece.RAILWAY_T, Rotation.R180)
    board.add_tile(5, 2, Piece.CORNER_STATION, Rotation.I, flip=True)
    board.add_tile(5, 3, Piece.RAILWAY_STRAIGHT, Rotation.I)
    board.add_tile(5, 6, Piece.RAILWAY_STRAIGHT, Rotation.R90)
    board.add_tile(6, 1, Piece.STRAIGHT_STATION, Rotation.I)
    board.add_tile(6, 3, Piece.RAILWAY_T, Rotation.R90)
    board.add_tile(6, 4, Piece.RAILWAY_STRAIGHT, Rotation.R90)
    board.add_tile(6, 5, Piece.CORNER_STATION, Rotation.R270, flip=False)
    return board

if __name__ == "__main__":

    board = rulebook_game()
    board.fancy_board_print()
    clusters = board.find_clusters()
    for cluster in clusters:
        print(cluster.get_start_count())
        print(cluster.get_cluster_tiles())
        print(cluster.get_frontier())
    print(board.get_used_special_routes())