from enum import Enum
from dataclasses import dataclass
from PIL import Image

NUM_ROWS = 7
NUM_COLS = 7
NUM_SPECIALS = 3

#photo measurements to get the positioning correct
TOP_OFFSET = 44
LEFT_OFFSET = 30
BOARD_WIDTH = 669
BOARD_HEIGHT = 669
SQUARE_WIDTH = BOARD_WIDTH//NUM_COLS
SQUARE_HEIGHT = BOARD_HEIGHT//NUM_ROWS

PHOTOS_FOLDER = "Railroad-Pictures/"

"""
Enum for the types of edges that can be on a piece
"""
class EdgeType(Enum):
    R = 0 #railway
    H = 1 #highway
    B = 2 #blank
    
    
    """
    returns the type of edge that clashes with this edge
    """
    @staticmethod
    def clash_type(edgeType):
        if edgeType == EdgeType.R:
            return EdgeType.H
        elif edgeType == EdgeType.H:
            return EdgeType.R
        else:
            raise ValueError("clashes only exist for highways and railways")
   
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
    #an overarching one for all the special tiles, to say we have a special tile
    SPECIAL = 20
    
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
    edgeType: EdgeType
    
"""
class for an edge between two squares, has the (row, col) of the start corner and then if 
vertical is True, goes downwards, if vertical is False, goes right
"""
class Edge:
    
    """
    Constructor.
    """
    def __init__(self, row, col, vertical):
        self._row = row
        self._col = col
        self._vertical = vertical
        
    """
    gets the edge given a piece and a side, this creates the same edge if two piece sides are touching
    e.g (1,1) is to the left of (1,2) so (1,1,RIGHT) and (1,2,LEFT) would have create the same edge
    """
    @staticmethod
    def get_edge_of_piece(row, col, side):
        if side == Side.TOP:
            return Edge(row, col, False)
        elif side == Side.RIGHT:
            return Edge(row, col + 1, True)
        elif side == Side.BOTTOM:
            return Edge(row + 1, col, False)
        elif side == Side.LEFT:
            return Edge(row, col, True)
        else:
            raise ValueError("invalid side argument")
        
    """
    override the equals function to use the row, col and vertical values to determine equality
    """
    def __eq__(self, obj):
        if not isinstance(obj, Edge):
            return False
        else:
            return self._row == obj._row and self._col == obj._col and self._vertical == obj._vertical
        
    """
    override the hash function for table look ups
    """
    def __hash__(self):
        return hash((self._row, self._col, self._vertical))
        
    """
    override the repr function to print nicely
    """
    def __repr__(self):
        return "({0},{1},{2})".format(self._row, self._col, "V" if self._vertical else "H")
    
    #GETTERS
    def get_row(self):
        return self._row
    
    def get_col(self):
        return self._col
    
    def is_vertical(self):
        return self._vertical
    
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
        Piece.RAILWAY_CORNER: (EdgeType.R, EdgeType.B, EdgeType.B, EdgeType.R),
        Piece.RAILWAY_T: (EdgeType.R, EdgeType.R, EdgeType.B, EdgeType.R),
        Piece.RAILWAY_STRAIGHT: (EdgeType.R, EdgeType.B, EdgeType.R, EdgeType.B),
        Piece.HIGHWAY_CORNER: (EdgeType.H, EdgeType.B, EdgeType.B, EdgeType.H),
        Piece.HIGHWAY_T: (EdgeType.H, EdgeType.H, EdgeType.B, EdgeType.H),
        Piece.HIGHWAY_STRAIGHT: (EdgeType.H, EdgeType.B, EdgeType.H, EdgeType.B),
        Piece.OVERPASS: (EdgeType.H, EdgeType.R, EdgeType.H, EdgeType.R),
        Piece.STRAIGHT_STATION: (EdgeType.R, EdgeType.B, EdgeType.H, EdgeType.B),
        Piece.CORNER_STATION: (EdgeType.R, EdgeType.B, EdgeType.B, EdgeType.H),
        Piece.THREE_H_JUNCTION: (EdgeType.H, EdgeType.H, EdgeType.R, EdgeType.H),
        Piece.THREE_R_JUNCTION: (EdgeType.H, EdgeType.R, EdgeType.R, EdgeType.R),
        Piece.HIGHWAY_JUNCTION: (EdgeType.H, EdgeType.H, EdgeType.H, EdgeType.H),
        Piece.RAILWAY_JUNCTION: (EdgeType.R, EdgeType.R, EdgeType.R, EdgeType.R),
        Piece.CORNER_JUNCTION: (EdgeType.H, EdgeType.R, EdgeType.R, EdgeType.H),
        Piece.CROSS_JUNCTION: (EdgeType.H, EdgeType.R, EdgeType.H, EdgeType.R),  
        Piece.START_RAILWAY: (EdgeType.R, EdgeType.B, EdgeType.B, EdgeType.B),
        Piece.START_HIGHWAY: (EdgeType.H, EdgeType.B, EdgeType.B, EdgeType.B),
        Piece.BLANK: (EdgeType.B, EdgeType.B, EdgeType.B, EdgeType.B),
        Piece.OVERPASS_RAILWAY: (EdgeType.B, EdgeType.R, EdgeType.B, EdgeType.R),
        Piece.OVERPASS_HIGHWAY: (EdgeType.H, EdgeType.B, EdgeType.H, EdgeType.B)
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
    
    _tile_variations = {
        Piece.RAILWAY_CORNER: (4, False),
        Piece.RAILWAY_T: (4, False),
        Piece.RAILWAY_STRAIGHT: (2, False),
        Piece.HIGHWAY_CORNER: (4, False),
        Piece.HIGHWAY_T: (4, False),
        Piece.HIGHWAY_STRAIGHT: (2, False),
        Piece.OVERPASS: (2, False),
        Piece.STRAIGHT_STATION: (4, False),
        Piece.CORNER_STATION: (4, True),
        Piece.THREE_H_JUNCTION: (4, False),
        Piece.THREE_R_JUNCTION: (4, False),
        Piece.HIGHWAY_JUNCTION: (1, False),
        Piece.RAILWAY_JUNCTION: (1, False),
        Piece.CORNER_JUNCTION: (4, False),
        Piece.CROSS_JUNCTION: (2, False),  
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
    get a list of all the possible variations of a given piece
    """
    @staticmethod
    def get_variations(piece):
        rotations, flip = Tile._tile_variations[piece]
        variations = []
        #apply each of the rotations to create new tiles
        for rotation_val in range(rotations):
            variations += [Tile(piece, Rotation(rotation_val))]
        #then if we can reverse it as well, do that
        if flip:
            for rotation_val in range(rotations):
                variations += [Tile(piece, Rotation(rotation_val), flip=True)]
        return variations
    
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
            return (self._piece == obj._piece and self._rotation == obj._rotation and self._flip == obj._flip)
    
    """
    override the representation function so printing is readable
    """
    def __repr__(self):
        return "({0},{1},{2},{3},{4},{5}{6})".format(self._piece.name, self._rotation.name, 
               self._dirs[Side.TOP].name, self._dirs[Side.RIGHT].name, self._dirs[Side.BOTTOM].name,
               self._dirs[Side.LEFT].name, ",flipped" if self._flip else "")
        
    """
    override the hash function to treat two tiles with the same piece types, rotation and flip as the same
    """
    def __hash__(self):
        return hash((self._piece, self._rotation, self._flip))
 
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
        self._cluster_reps = None
        self._clusters_up_to_date = False #keeps track of whether the currently stored clusters are up to date
        self._solution_tiles = []
      
    """
    add a tile to the board
    """
    def add_tile(self, row, col, piece, rotation, flip=False):
        self._board[row][col] = Tile(piece, rotation, flip)
        if piece in SPECIAL_PIECES:
            self._special_routes += [piece]
        self._clusters_up_to_date = False #if any tiles are added, the clustering is invalid
        
    """
    add a solution tile to the board, treated like a normal tile, but will be printed with a light green overlay
    """
    def add_solution_tile(self, row, col, tile):
        self._solution_tiles += [(row, col, tile)]
        
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
    def fancy_board_print(self, file=None, show_free_squares=False):
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
        
        #now if we are displaying the free squares, do so
        if show_free_squares:
            free_squares = self.get_free_squares()
            for square in free_squares:
                row = square[0]
                col = square[1]
                square_im = Image.new("RGB", (SQUARE_WIDTH//2, SQUARE_HEIGHT//2),  color="green")
                im.paste(square_im, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS + SQUARE_WIDTH//4, 
                                     TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS + SQUARE_HEIGHT//4))
        
        #add the solution tiles
        for row, col, tile in self._solution_tiles:
            piece_image = tile.get_image()
            im.paste(piece_image, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS, TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS))
            solution_overlay = Image.new("RGB", (SQUARE_WIDTH//4, SQUARE_HEIGHT//4), color="blue")
            im.paste(solution_overlay, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS, 
                                        TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS))
        
        
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
        
        #update the knowledge of the clusters
        self._cluster_reps = cluster_reps
        self._clusters_up_to_date = True
        
        #we are going to need the free squares in various different places, so work them out once initially
        self._determine_free_squares()
        
        return cluster_reps
    
    """
    finds and stores the list of all free squares on the board
    """
    def _determine_free_squares(self):
        self._free_squares = []
        for cluster_rep in self._cluster_reps:
            if cluster_rep.is_free_blank_cluster():
                #take off the tile element, we only care about locations
                for row, col, tile in cluster_rep.get_cluster_tiles():
                    self._free_squares += [(row, col)]       
    
    """
    get all the squares which pieces could be placed in, returns a list of (row, col) pairs
    """
    def get_free_squares(self):
        #check if the clusters are up to date and if not, update them
        if not self._clusters_up_to_date:
            self.find_clusters()
        return self._free_squares
        
    """
    returns a list of (edge, edgeType) pairs corresponding to the ends of each of the clusters
    """
    def get_all_cluster_ends(self):
        #check if the clusters are up to date and if not, update them
        if not self._clusters_up_to_date:
            self.find_clusters()
        
        #now go through all the clusters, and the frontiers and gather the edges they are on
        cluster_ends = []
        for cluster_rep in self._cluster_reps:
            if not cluster_rep.is_blank_cluster():
                for clusterEdge in cluster_rep.get_frontier():
                    cluster_ends += [(Edge.get_edge_of_piece(clusterEdge.row, clusterEdge.col, clusterEdge.side), 
                                      clusterEdge.edgeType)]
        return cluster_ends
    
    """
    returns a list of edges corresponding to all the internal edges that are available
    """
    def get_available_internal_edges(self):
        free_squares = self.get_free_squares()
        edges = []
        #iterate through them all and check for right and down
        #this is a brute force search which could be sped up BUT it is a really small search and won't take long anyway
        for row, col in free_squares:
            #first check to the right
            if (row, col + 1) in free_squares:
                edges += [Edge.get_edge_of_piece(row, col, Side.RIGHT)]
            if (row + 1, col) in free_squares:
                edges += [Edge.get_edge_of_piece(row, col, Side.BOTTOM)]
        return edges
    
    """
    get all the paths between clusters
    returns a list of all cluster identifiers and a dictionary of all the paths between the pairs.
    Note that the pairs are only found in pairs that increase e.g defined for (1,2) not (2,1)
    """
    def get_cluster_paths(self):
        #check if the clusters are up to date and if not, update them
        if not self._clusters_up_to_date:
            self.find_clusters()
        
        #first do a small amount of processing to get the clusters we are interested in
        cluster_identifiers = [] #list of all the clusters with pieces in them
        identifier_to_cluster = {}
        for cluster in self._cluster_reps:
            #only care about non-blank clusters with points to connect to
            if not cluster.is_blank_cluster() and len(cluster.get_frontier()) > 0:
                cluster_identifiers += [cluster.get_identifier()]
                identifier_to_cluster[cluster.get_identifier()] = cluster
                
        cluster_identifiers.sort()
        print(cluster_identifiers)
                
        #next create a dictionary for identifying whether a particular piece has a cluster edge
        edges = {}
        for c_id in cluster_identifiers:
            cluster = identifier_to_cluster[c_id]
            for clusterEdge in cluster.get_frontier():
                edges[(clusterEdge.row, clusterEdge.col, clusterEdge.side)] = c_id
                
        #next determine all the paths from each start location
        free_square_set = set(self.get_free_squares()) #lots of lookups, make a set
        paths = {}
        for c_id in cluster_identifiers:
            cluster = identifier_to_cluster[c_id]
            for clusterEdge in cluster.get_frontier():
                #use a DFS to find all paths leaving from this cluster edge and running into other clusters
                edgePaths = self._path_dfs(c_id, [(clusterEdge.row, clusterEdge.col, clusterEdge.side)], edges, free_square_set)
                #go through all found paths and add them to the full collection
                for finish_id, path in edgePaths:
                    #if there are no paths currently found between these two clusters, add them
                    if paths.get((c_id, finish_id)) == None:
                        paths[c_id, finish_id] = []
                    paths[c_id, finish_id] += [path]
        return cluster_identifiers, paths
        
       
    """
    given a row, col and side, returns a (row, col, side) tuple that is the other side of the same edge.
    e.g (0,0,RIGHT) shares an edge with (0,1,LEFT)
    """
    @staticmethod
    def opposite_edge(row, col, side):
        if side == Side.TOP:
            return row - 1, col, Side.BOTTOM
        elif side == Side.RIGHT:
            return row, col + 1, Side.LEFT
        elif side == Side.BOTTOM:
            return row + 1, col, Side.TOP
        elif side == Side.LEFT:
            return row, col - 1, Side.RIGHT
        else:
            raise ValueError("cannot take the opposite edge of the given side")
        
    """
    use DFS to determine all the paths that continue from a location and run into a cluster edge
    of a cluster different to the cluster with the start_cluster_id
    path is a list of (row, col, Side) tuples tracing the path
    returns a list of (id, path) tuples with the end cluster id and the path taken to get there
    """       
    def _path_dfs(self, start_cluster_id, path, edges, free_square_set):
        #get the last edge
        last_edge = path[-1]
        #translate this to the other side of the edge, which is where the next piece must go
        row, col, side = Board.opposite_edge(last_edge[0], last_edge[1], last_edge[2])
        
        #if this opposite edge is a cluster edge, we have a valid path and we can stop here
        opposite_edge_id = edges.get((row, col, side))
        if opposite_edge_id != None:
            #to only add each path in one direction, always go in the increasing id direction
            if opposite_edge_id > start_cluster_id:
                return [(edges.get((row, col, side)), path)]
            else:
                return []
        
        #another base case is if we have gone too far
        if len(path) >= 6: #MAGIC NUMBER, REMOVE LATER
            return [] #there are no paths to return
        
        #check we aren't retracing at all
        for r, c, s in path:
            if row == r and col == c:
                return []
        
        #can only continue if the square is a free set
        if (row, col) in free_square_set:
            paths = []
            for next_side in Side:
                if next_side != side:
                    paths += self._path_dfs(start_cluster_id, list(path) + [(row, col, next_side)], edges, free_square_set)
            return paths
        else: #this is not a square that we can continue on
            return []
     
    """
    determines the static score associated with placing the given tile at (row, col)
    -1 for any rail/highway that runs into an occupied square with a blank side
    +1 for any placement that connects to a rail/highway on another piece that isn't a start highway or railway
    Assumes that the given placement is valid and square is a (row, col) pair
    """
    def placement_score(self, square, tile):
        score = 0 #initialise the score to zero and then score going around the different sides
        row, col = square
        for side in Side:
            #we can only gain or lose points on edges that aren't blank
            if tile.get_edge_type_on_side(side) != EdgeType.B:
                #get the opposite side of the edge and the tile that is there
                opp_row, opp_col, opp_side = Board.opposite_edge(row, col, side)
                #check if we are in the board, if the opposite edge is outside the board, it doesn't matter what we connect to it
                #this applies if it is a start edge or not
                if opp_row >= 0 and opp_row < NUM_ROWS and opp_col >= 0 and opp_col < NUM_COLS:
                    opp_tile = self._board[opp_row][opp_col]
                    #then if this other piece is not blank, check what is on the other side
                    #if it is blank, then this will be a dynamic placement score not a static score, so ignore
                    if opp_tile.get_piece() != Piece.BLANK:
                        opp_edge_type = opp_tile.get_edge_type_on_side(opp_side)
                        if opp_edge_type == EdgeType.B:
                            #if we have a non blank edge and its running into a blank edge, that will end in an error
                            score -= 1 
                        else:
                            #well we know this is a valid placement by our assumption, so as long as what we are connecting
                            #to is not one of the start edges (which we know it isn't from a previous check), we are removing 
                            #a hanging error from the board (maybe moving it but that is the dynamic errors problem)
                            score += 1
        #return the score
        return score
    
    """
    returns whether a square is one of the centre squares
    s is a square, i.e a (row, col) tuple
    """
    @staticmethod
    def is_centre_square(s):
        return (s[0] >= 2 and s[0] <= 4 and s[1] >= 2 and s[1] <= 4)
     
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
                edgeType = tile.get_edge_type_on_side(side)
                if edgeType != EdgeType.B:
                    self._frontier += [ClusterEdge(row, col, side, edgeType)]

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
        edgeType1 = tile1._tile.get_edge_type_on_side(side)
        edgeType2 = tile2._tile.get_edge_type_on_side(Side.opposite(side))
        
        #now find the element of the frontier of each of them
        #there is only an element on the frontier if it's not a blank edge
        #these may not be defined, but they aren't used unless they are defined
        #there is an edge case when processing overpasses that this edge may have been added to another cluster
        #and removed from consideration, there is a check for that edge case as well
        if edgeType1 != EdgeType.B and not (isOverpass2 and edgeType2 == EdgeType.B):
            frontierEdge1 = representative1._find_in_frontier(tile1._row, tile1._col, side)
        if edgeType2 != EdgeType.B and not (isOverpass1 and edgeType1 == EdgeType.B):
            frontierEdge2 = representative2._find_in_frontier(tile2._row, tile2._col, Side.opposite(side))
        
        #consider the cases with two blank clusters, they will get joined together
        if representative1._blank_cluster and representative2._blank_cluster:
            #if both clusters are blank clusters, join them together
            Cluster._join_clusters(representative1, representative2)
        #check for if there is one blank cluster and the other isn't
        elif representative1._blank_cluster and not representative2._blank_cluster:
            #if there is an edge leading into the blank cluster though, add it
            #this allows us to detect detached squares
            if edgeType2 != EdgeType.B:
                representative1._frontier += [frontierEdge2]
        elif representative2._blank_cluster and not representative1._blank_cluster:
            if edgeType1 != EdgeType.B:
                representative2._frontier += [frontierEdge1]
        #at this point in the chain, they are both not blank clusters
        #if they are the same we will be joining the clusters together, remove the edges that joined them together
        elif (edgeType1 == EdgeType.H and edgeType2 == EdgeType.H) or (edgeType1 == EdgeType.R and edgeType2 == EdgeType.R):
            representative1._remove_from_frontier(frontierEdge1)
            representative2._remove_from_frontier(frontierEdge2)
            Cluster._join_clusters(representative1, representative2)
        #if they have clashes, then this is a problem and raise an error to say that this board is invalid
        elif (edgeType1 == EdgeType.H and edgeType2 == EdgeType.R) or (edgeType1 == EdgeType.R and edgeType2 == EdgeType.H):
            raise ValueError("board invalid - clash between ({0},{1}) and ({2},{3})".format(
                    tile1._row, tile1._col, tile2._row, tile2._col))
        #if we have a non-blank running into a blank (but neither are blank clusters), remove the side running into the
        #blank from the cluster, because we won't ever be able to join to it, this is a -1 point, but we are only
        #interested in point changes
        #don't do this for overpass segments, because there is 'another' tile there
        elif edgeType1 == EdgeType.B and not isOverpass1 and edgeType2 != EdgeType.B:
            representative2._remove_from_frontier(frontierEdge2)
        elif edgeType2 == EdgeType.B and not isOverpass2 and edgeType1 != EdgeType.B:
            representative1._remove_from_frontier(frontierEdge1)
            
            
    #GETTER METHODS
    
    """
    return whether this cluster object is the representative element of its cluster set
    """
    def is_representative(self):
        return self._parent == self
    
    """
    return whether a cluster can have new pieces placed in it
    """
    def is_free_blank_cluster(self):
        #a cluster can have pieces placed in it if it is blank and is not isolated
        #elements are added to the frontier for connections, if the frontier is empty
        #it is isolated
        return self.is_blank_cluster() and len(self._frontier) > 0
    
    def get_row(self):
        return self._row
    
    def get_col(self):
        return self._col
    
    def get_parent(self):
        return self._parent
    
    def is_blank_cluster(self):
        return self._blank_cluster
    
    def get_cluster_tiles(self):
        return self._cluster_tiles
        
    def get_frontier(self):
        return self._frontier
    
    def get_start_count(self):
        return self._start_count
    
    """
    get an identifier for the cluster, this will be a unique number for each cluster
    """
    def get_identifier(self):
        return 200 * self._tile.get_piece().value + 10*self._row + self._col
    
    """
    recover the position of the piece from the identifier
    """
    @staticmethod
    def recover_from_identifier(idtfr):
        return (idtfr + 10) % 200 // 10 - 1, (idtfr + 1) % 200 % 10 - 1
        
        

"""
class containing information about all the possible moves from a given set of pieces
"""
class Moves:
    
    """
    Constructor.
    Takes the given pieces and creates all the necessary data structures for accesses to this class
    """
    def __init__(self, pieces, used_specials):
        self._pieces = []
        self._piece_count = {}
        self._variations = {}
        self._all_possible_moves = []
        #add unique pieces to the list of pieces and keep a count of how many of each there are
        for piece in pieces:
            if piece not in self._piece_count:
                self._pieces += [piece]
                self._piece_count[piece] = 1
                variations = Tile.get_variations(piece)
                self._variations[piece] = variations
                self._all_possible_moves += variations
            else:
                self._piece_count[piece] += 1
              
        #determine all the possible special piece placements
        if len(used_specials) < NUM_SPECIALS:
            self._pieces += [Piece.SPECIAL]
            self._piece_count[Piece.SPECIAL] = 1
            self._variations[Piece.SPECIAL]  = []
            for piece in SPECIAL_PIECES:
                if piece not in used_specials:
                    self._variations[Piece.SPECIAL] += Tile.get_variations(piece)
                
            #add these to the all possible moves list
            self._all_possible_moves += self._variations[Piece.SPECIAL]

    def get_pieces(self):
        return self._pieces
    
    def get_variations(self, piece):
        return self._variations[piece]
    
    def get_piece_count(self, piece):
        return self._piece_count[piece]
    
    def get_all_possible_moves(self):
        return self._all_possible_moves


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

"""
the pieces available on the last turn of the default game, pass it the board for the specials
"""
def rulebook_moves(board):
    return Moves([Piece.RAILWAY_STRAIGHT, Piece.OVERPASS, Piece.RAILWAY_CORNER, Piece.HIGHWAY_STRAIGHT], 
                 board.get_used_special_routes())

if __name__ == "__main__":

    board = rulebook_game()
    board.fancy_board_print(show_free_squares=True)

    #clusters = board.find_clusters()
    #for cluster in clusters:
        #print(cluster.get_start_count())
        #print(cluster.get_cluster_tiles())
        #print(cluster.get_frontier())
    #print(board.get_used_special_routes())
    
    #print(board.get_free_squares())
    #print(board._get_cluster_representatives)
    
    #board.get_cluster_paths()
    