from enum import Enum
from dataclasses import dataclass
from PIL import Image
from time import sleep

NUM_ROWS = 7
NUM_COLS = 7

#photo measurements to get the positioning correct
TOP_OFFSET = 44
LEFT_OFFSET = 30
BOARD_WIDTH = 669
BOARD_HEIGHT = 669

PHOTOS_FOLDER = "Railroad-Pictures/"

class Edge(Enum):
    R = 0 #railway
    H = 1 #highway
    B = 2 #blank
    
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
    
class Orientation(Enum):
    DEFAULT = 0
    #turns considered clockwise
    TURN_90 = 1
    TURN_180 = 2
    TURN_270 = 3
    
class Side(Enum):
    TOP = 0
    RIGHT = 1
    BOTTOM = 2
    LEFT = 3
    
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
highway_start_positions = [(-1, 1, Orientation.TURN_180), (-1, 5, Orientation.TURN_180),
                           (3, -1, Orientation.TURN_90), (3, NUM_COLS, Orientation.TURN_270),
                           (NUM_ROWS, 1, Orientation.DEFAULT), (NUM_ROWS, 5, Orientation.DEFAULT)]
railway_start_positions = [(-1, 3, Orientation.TURN_180), (NUM_ROWS, 3, Orientation.DEFAULT),
                           (1, -1, Orientation.TURN_90), (5, -1, Orientation.TURN_90),
                           (1, NUM_COLS, Orientation.TURN_270), (5, NUM_COLS, Orientation.TURN_270)]

class Tile:
    
    #map of all the tiles in their default orientation
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
        Piece.CORNER_STATION: "corner-station.png",
        Piece.THREE_H_JUNCTION: "three-h-junction",
        Piece.THREE_R_JUNCTION: "three-r-junction",
        Piece.HIGHWAY_JUNCTION: "highway-junction",
        Piece.RAILWAY_JUNCTION: "railway-junction",
        Piece.CORNER_JUNCTION: "corner-junction",
        Piece.CROSS_JUNCTION: "cross-junction",             
    }
    
    """
    Constructor
    """
    def __init__(self, piece, orientation):
        self._piece = piece
        self._orientation = orientation
        #load in all the left, right, down, up and overpass values
        #load these upon creation because they will be accessed multiple times
        self._dirs = {}
        self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM], self._dirs[Side.LEFT] = self._tile_map[piece]
        self._rotate(orientation)
        
    """
    rotate the tile to the given orientation, assumes in default orientation
    """
    def _rotate(self, orientation):
        #rotate to the given orientation, enum values are the number of rotations required
        for rotations in range(orientation.value):
            #change all the assignments in the same line, handles the required temporary variables
            self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM], self._dirs[Side.LEFT] = \
                    self._dirs[Side.LEFT], self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM]
         
    """
    get the image associated with this piece and orientation, scaled to fit on the board image
    """
    def get_image(self):
        #get the correct image
        piece_image = Image.open(PHOTOS_FOLDER + self._tile_pics[self._piece])
        #resize the image
        piece_image = piece_image.resize([BOARD_WIDTH//NUM_COLS, BOARD_HEIGHT//NUM_ROWS], Image.ANTIALIAS)
        #rotate the image
        if self._orientation == Orientation.TURN_90:
            piece_image.rotate(90)
        elif self._orientation == Orientation.TURN_180:
            piece_image.rotate(180)
        elif self._orientation == Orientation.TURN_270:
            piece_image.rotate(270)
        return piece_image
    
    """
    get the edge type associated with one of the directions
    """
    def get_edge_type_on_side(self, side):
        return self._dirs[side]
    
    def get_piece(self):
        return self._piece
    
    def get_orientation(self):
        return self._orientation
    
    def get_overpass(self):
        return self._piece == Piece.OVERPASS
    
    """
    override the equality function to treat two Tiles with the same value the same
    """
    def __eq__(self, obj):
        if not isinstance(obj, Tile):
            return False
        else:
            return (self.piece == obj.piece and self.orientation == obj.orientation)
    
    """
    override the representation function so printing is readable
    """
    def __repr__(self):
        return "({0},{1},{2},{3},{4},{5})".format(self._piece.name, self._orientation.name, 
               self._dirs[Side.TOP].name, self._dirs[Side.RIGHT].name, self._dirs[Side.BOTTOM].name,
               self._dirs[Side.LEFT].name)
    
class Board:
    
    def __init__(self):
        #create an empty board with no tiles in it yet
        self._board = [[Tile(Piece.BLANK, Orientation.DEFAULT)]*NUM_COLS for i in range(NUM_ROWS)]
        self._initialise_start_tiles()
      
    """
    add a tile to the board
    """
    def add_tile(self, row, col, piece, orientation):
        self._board[row][col] = Tile(piece, orientation)
        
    """
    add a start tile to the board, these are the pieces around the edge
    """
    def _add_start_tile(self, row, col, piece, orientation):
        self._start_tiles += [(row, col, Tile(piece, orientation))]
        
    """
    initialise all the start pieces
    """
    def _initialise_start_tiles(self):
        self._start_tiles = []
        for row, col, orientation in railway_start_positions:
            self._add_start_tile(row, col, Piece.START_RAILWAY, orientation)
        for row, col, orientation in highway_start_positions:
            self._add_start_tile(row, col, Piece.START_HIGHWAY, orientation)
        
    """
    creates an image corresponding to the board,
    file - the location to store the new image, if the file is None, displays it
    """
    def fancy_board_print(self, file=None):
        #create a new image with the board in the background
        board = Image.open(PHOTOS_FOLDER + "board.png")
        im = Image.new('RGB', board.size)
        im.paste(board, (0,0))
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
            
            
    def initialise_clusters(self):
        clusters = []
        for row in range(NUM_ROWS):
            row_clusters = []
            for col in range(NUM_COLS):
                tile = self._board[row][col]
                #if the piece is an overpass, treat it as two separate tiles for clustering
                if tile.get_piece() == Piece.OVERPASS:
                    railway_tile = Tile(Piece.OVERPASS_RAILWAY, tile.get_orientation())
                    highway_tile = Tile(Piece.OVERPASS_HIGHWAY, tile.get_orientation())
                    row_clusters += [[Cluster(row, col, railway_tile), Cluster(row, col, highway_tile)]]
                else:
                    row_clusters += [[Cluster(row, col, tile)]] #this is a list of clusters to handle overpasses
            clusters += [row_clusters]
        return clusters
            
    def find_clusters(self):
        #first create clusters for all of the start tiles and all the tiles on the board
        start_clusters = []
        for row, col, tile in self._start_tiles:
            start_clusters += [Cluster(row, col, tile)]
        #then create clusters for all of the actual tiles
        clusters = self.initialise_clusters()
        
        #first process all the start clusters
        for start_cluster in start_clusters:
            if start_cluster.row == -1: #these are the top clusters
                for other_cluster in clusters[start_cluster.get_row() + 1][start_cluster.get_col()]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.BOTTOM)
            elif start_cluster.row == NUM_ROWS: #these are the ones on the bottom
                for other_cluster in clusters[start_cluster.get_row() - 1][start_cluster.get_col()]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.TOP)
            elif start_cluster.col == -1: #the ones on the left
                for other_cluster in clusters[start_cluster.get_row()][start_cluster.get_col() + 1]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.RIGHT)
            elif start_cluster.col == NUM_COLS: #on the right
                for other_cluster in clusters[start_cluster.get_row()][start_cluster.get_col() - 1]:
                    Cluster.try_join_clusters(start_cluster, other_cluster, Side.LEFT)
                    
        #next process all the other clusters, only reach up and left, since each pair only needs to be done once
        
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                print(row, col)
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
                                                   
        
        #find all the representative elements of the clusters, these have parents that are None       
        final_clusters = []
        for cluster in start_clusters:
            if cluster.is_representative():
                final_clusters += [cluster]
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                for cluster in clusters[row][col]:
                    if cluster.is_representative():
                        final_clusters += [cluster]
                        
        return final_clusters
                                             
                
        
        

   
"""
A cluster of adjoining pieces in the form of a disjoint set, 
stores all the information about the cluster in the top level element in the disjoint set
"""
class Cluster:
    
    """
    initialise a cluster with just one tile at the given location
    """
    def __init__(self, row, col, tile):
        self.rank = 1 #the max height of the disjoint cluster set
        self.parent = self
        self.tile = tile
        self.row = row
        self.col = col
        self.blank_cluster = (tile.get_piece() == Piece.BLANK) #whether this cluster is a blank cluster or a tiled cluster
        self.cluster_tiles = [(row, col, tile)]
        
        #add all the edges of the cluster
        self.frontier = []
        if not self.blank_cluster:
            for side in Side:
                edge = tile.get_edge_type_on_side(side)
                if edge != Edge.B:
                    self.frontier += [ClusterEdge(row, col, side, edge)]

    """
    find the representative element of the disjoint set containing this tile cluster
    applies the path compression heuristic
    """     
    def find_set(self):
        if self.parent != self:
            self.parent = self.parent.find_set()
        return self.parent
    
    """
    find an element of the frontier corresponding to the given row, column and side
    """
    def find_in_frontier(self, row, col, side):
        for ce in self.frontier:
            if ce.row == row and ce.col == col and ce.side == side:
                return ce
        raise ValueError("{0}, {1}, {2} not found in frontier".format(row, col, side.name))
        
    """
    remove an element from the frontier
    """
    def remove_from_frontier(self, ce):
        self.frontier.remove(ce)
            
        
    """
    actually merge two clusters together given their representative elements
    """
    @staticmethod
    def _join_clusters(representative1, representative2):
        #do this with the union by rank heuristic to ensure the clusters keep depth low
        if representative1.rank > representative2.rank:
            representative2.parent = representative1 #point cluster 2 to cluster 1
            #merge the frontier and cluster tiles list together so that rep 1 has all the joined information
            representative1.frontier += representative2.frontier
            representative1.cluster_tiles += representative2.cluster_tiles
        else:
            representative1.parent = representative2
            representative2.frontier += representative1.frontier
            representative2.cluster_tiles += representative1.cluster_tiles
            #increase the rank if they were the same
            if representative1.rank == representative2.rank:
                representative2.rank += 1 

        
    """
    join the clusters that tile1 and tile2 are in (not necessarily representative elements)
    side - the side of tile1 that tile2 is supposed to be on, this function assumes that the given tiles are adjacent
    returns False if the two entered broke the game rules
    """
    @staticmethod
    def try_join_clusters(tile1, tile2, side):
        print(tile1.row, tile1.col, tile2.row, tile2.col)
        #get the representative element of each of the tiles
        representative1 = tile1.find_set()
        representative2 = tile2.find_set()
        #if they are already in the same cluster, don't join them again
        if representative1 == representative2:
            return
        
        #get the edge types out because they will be used a lot and are long
        edge1 = tile1.tile.get_edge_type_on_side(side)
        edge2 = tile2.tile.get_edge_type_on_side(Side.opposite(side))
        
        #now find the element of the frontier of each of them
        #there is only an element on the frontier if it's not a blank edge
        #these may not be defined, but they aren't used unless they are defined
        if edge1 != Edge.B:
            frontierEdge1 = representative1.find_in_frontier(tile1.row, tile1.col, side)
        if edge2 != Edge.B:
            frontierEdge2 = representative2.find_in_frontier(tile2.row, tile2.col, Side.opposite(side))
        
        #consider the cases with two blank clusters, they will get joined together
        if representative1.blank_cluster and representative2.blank_cluster:
            print("A")
            #if both clusters are blank clusters, join them together
            Cluster._join_clusters(representative1, representative2)
        #check for if there is one blank cluster and the other isn't
        elif representative1.blank_cluster and not representative2.blank_cluster:
            print("B")
            #if there is an edge leading into the blank cluster though, add it
            #this allows us to detect detached squares
            if edge2 != Edge.B:
                representative1.frontier += [frontierEdge2]
        elif representative2.blank_cluster and not representative1.blank_cluster:
            print("C")
            if edge1 != Edge.B:
                representative2.frontier += [frontierEdge1]
        #at this point in the chain, they are both not blank clusters
        #if they are the same we will be joining the clusters together, remove the edges that joined them together
        elif (edge1 == Edge.H and edge2 == Edge.H) or (edge1 == Edge.R and edge2 == Edge.R):
            print("D")
            representative1.remove_from_frontier(frontierEdge1)
            representative2.remove_from_frontier(frontierEdge2)
            Cluster._join_clusters(representative1, representative2)
        #if they have clashes, then this is a problem and raise an error to say that this board is invalid
        elif (edge1 == Edge.H and edge2 == Edge.R) or (edge1 == Edge.R and edge2 == Edge.H):
            print("E")
            raise ValueError("board invalid - clash between ({0},{1}) and ({2},{3})".format(
                    tile1.row, tile1.col, tile2.row, tile2.col))
        #otherwise we have at least one blank joining non blank clusters, keep them detached
            
        #otherwise there were two tiled clusters, without a valid join between them, in this case leave them separate
    
    def get_row(self):
        return self.row
    
    def get_col(self):
        return self.col
    
    def get_parent(self):
        return self.parent
    
    def is_representative(self):
        return self.parent == self
        
        
            

if __name__ == "__main__":

    board = Board()
    board.add_tile(2,3, Piece.RAILWAY_CORNER, Orientation.DEFAULT)
    #board.fancy_board_print()
    clusters = board.find_clusters()
    for cluster in clusters:
        print(cluster.cluster_tiles)
    
    print(Side.opposite(Side.TOP))
