from enum import Enum, IntEnum
from dataclasses import dataclass
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

NUM_ROWS = 7
NUM_COLS = 7
NUM_SPECIALS = 3
NUM_STARTS = 12

LONGEST_POSSIBLE_PATH = 33

#photo measurements to get the positioning correct
TOP_OFFSET = 44
LEFT_OFFSET = 30
BOARD_WIDTH = 669
BOARD_HEIGHT = 669
SQUARE_WIDTH = BOARD_WIDTH//NUM_COLS
SQUARE_HEIGHT = BOARD_HEIGHT//NUM_ROWS

PHOTOS_FOLDER = "Railroad-Pictures/"

TURN_COLOURS = ["lightcoral", "cornflowerblue", "lightseagreen", "slateblue", "orchid", "palegreen", "orangered"]

"""
Enum for the types of edges that can be on a piece
"""
class EdgeType(IntEnum):
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
class Piece(IntEnum):
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
    #an overarching one for all the basic and junction tiles, to say we have a basic or junction tile
    BASIC = 21
    JUNCTION = 22
    
    
#grouping of pieces
BASIC_PIECES = [Piece.RAILWAY_CORNER, Piece.RAILWAY_T, Piece.RAILWAY_STRAIGHT,
                Piece.HIGHWAY_CORNER, Piece.HIGHWAY_T, Piece.HIGHWAY_STRAIGHT]
JUNCTION_PIECES = [Piece.OVERPASS, Piece.STRAIGHT_STATION, Piece.CORNER_STATION]
SPECIAL_PIECES = [Piece.THREE_H_JUNCTION, Piece.THREE_R_JUNCTION, Piece.HIGHWAY_JUNCTION,
                  Piece.RAILWAY_JUNCTION, Piece.CORNER_JUNCTION, Piece.CROSS_JUNCTION]
SWITCH_PIECES = [Piece.STRAIGHT_STATION, Piece.CORNER_STATION, Piece.THREE_H_JUNCTION, 
                 Piece.THREE_R_JUNCTION, Piece.CORNER_JUNCTION, Piece.CROSS_JUNCTION]
POSSIBLE_MOVES = BASIC_PIECES + JUNCTION_PIECES + SPECIAL_PIECES
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
class Side(IntEnum):
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
        elif side == Side.LEFT:
            return Side.RIGHT
        else:
            raise ValueError("invalid argument")
        
#start locations of all the highways and railways
HIGHWAY_START_POSITIONS = [(-1, 1, Rotation.R180), (-1, 5, Rotation.R180),
                           (3, -1, Rotation.R90), (3, NUM_COLS, Rotation.R270),
                           (NUM_ROWS, 1, Rotation.I), (NUM_ROWS, 5, Rotation.I)]
RAILWAY_START_POSITIONS = [(-1, 3, Rotation.R180), (NUM_ROWS, 3, Rotation.I),
                           (1, -1, Rotation.R90), (5, -1, Rotation.R90),
                           (1, NUM_COLS, Rotation.R270), (5, NUM_COLS, Rotation.R270)]

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
    override the equals operator
    """
    def __eq__(self, obj):
        if not isinstance(obj, ClusterEdge):
            return False
        else:
            return (self.row == obj.row and self.col == obj.col and self.side == obj.side and self.edgeType == obj.edgeType)
        
    """
    override the hash function to treat two cluster edges with the same values as the same 
    """
    def __hash__(self):
        return hash((self.row, self.col, self.side, self.edgeType))
    
    """
    override the repr function to make any printing nicer
    """
    def __repr__(self):
        return "CE({0}, {1}, {2}, {3})".format(self.row, self.col, self.side.name, self.edgeType.name)

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
        Piece.START_HIGHWAY: (4,False),
        Piece.START_RAILWAY: (4,False)
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
        #start by unpacking any multi piece signals
        if piece == Piece.SPECIAL:
            variations = []
            for piece in SPECIAL_PIECES:
                variations += Tile.get_variations(piece)
        elif piece == Piece.BASIC:
            variations = []
            for piece in BASIC_PIECES:
                variations += Tile.get_variations(piece)
        elif piece == Piece.JUNCTION:
            variations = []
            for piece in JUNCTION_PIECES:
                variations += Tile.get_variations(piece)
        else:
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
    get a list of all variations of all pieces
    """
    @staticmethod
    def get_all_variations():
        all_variations = []
        for piece in POSSIBLE_MOVES + START_PIECES:
            all_variations += Tile.get_variations(piece)
        return all_variations
    
    """
    determine how many ends of the tile are on internal edges of the board if placed at position s
    loose ends are only counted on the right and bottom edges, so they aren't double counted
    """
    def loose_ends(self, s):
        count = 0
        if self.get_edge_type_on_side(Side.TOP) != EdgeType.B and s[0] > 0:
            count += 1
        if self.get_edge_type_on_side(Side.RIGHT) != EdgeType.B and s[1] < NUM_COLS - 1:
            count += 1
        if self.get_edge_type_on_side(Side.BOTTOM) != EdgeType.B and s[0] < NUM_ROWS - 1:
            count += 1
        if self.get_edge_type_on_side(Side.LEFT) != EdgeType.B and s[1] > 0:
            count += 1
        return count
    
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
    
    def get_flip(self):
        return self._flip
    
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
        self._board = {}
        self._turn = {} #the turn which a piece was placed on
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self._board[row,col] = Tile(Piece.BLANK, Rotation.I)
        self._initialise_start_tiles()
        self._specials_used = set()
        #cluster initialisers
        self._clusters_up_to_date = False
        self._cluster_reps = None
      
    """
    add a tile to the board at the given square
    the turn (if important) is given, only don't supply a turn if this is a dummy entry in the callback
    """
    def add_tile(self, tile, square, turn=-1):
        self._board[square] = tile
        self._turn[square] = turn
        if tile.get_piece() in SPECIAL_PIECES:
            self._specials_used.add(tile.get_piece())
        self._clusters_up_to_date = False
        
    """
    remove the tile at the given square from the board
    """
    def remove_tile(self, square):
        if self._board[square].get_piece() in SPECIAL_PIECES:
            self._specials_used.remove(self._board[square].get_piece())
        self._board[square] = Tile(Piece.BLANK, Rotation.I)
        if square in self._turn:
            self._turn.pop(square)
        self._clusters_up_to_date = False
        
    """
    initialise all the start pieces
    """
    def _initialise_start_tiles(self):
        for row, col, rotation in RAILWAY_START_POSITIONS:
            self._board[row,col] = Tile(Piece.START_RAILWAY, rotation)
        for row, col, rotation in HIGHWAY_START_POSITIONS:
            self._board[row,col] = Tile(Piece.START_HIGHWAY, rotation)
        
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
                if self._board[row,col].get_piece() != Piece.BLANK:
                    #get the image itself
                    piece_image = self._board[row,col].get_image()
                    
                    #draw a number overlay
                    txt = Image.new("RGB", (piece_image.size[0]//4, piece_image.size[1]//4), color=TURN_COLOURS[self._turn[row,col]-1])
                    d = ImageDraw.Draw(txt)
                    fnt = ImageFont.truetype(PHOTOS_FOLDER + "arial.ttf", 22)
                    d.text((5,0), str(self._turn[row,col]), font=fnt, fill=(0,0,0))
                    piece_image.paste(txt, (piece_image.size[1]*3//4, 0))
                    im.paste(piece_image, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS, TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS))

        #now display the image, depending on if a file is given
        if file == None:
            im.show()
        else:
            im.save(file)
        
    """
    given a square and side, returns a (square, side) tuple that is the other side of the same edge.
    e.g (0,0,RIGHT) shares an edge with (0,1,LEFT)
    """
    @staticmethod
    def opposite_edge(s, side):
        if side == Side.TOP:
            return (s[0] - 1, s[1]), Side.BOTTOM
        elif side == Side.RIGHT:
            return (s[0], s[1] + 1), Side.LEFT
        elif side == Side.BOTTOM:
            return (s[0] + 1, s[1]), Side.TOP
        elif side == Side.LEFT:
            return (s[0], s[1] - 1), Side.RIGHT
        else:
            raise ValueError("cannot take the opposite edge of the given side")
    
    """
    returns whether a square is one of the centre squares
    s is a square, i.e a (row, col) tuple
    """
    @staticmethod
    def is_centre_square(s):
        return (s[0] >= 2 and s[0] <= 4 and s[1] >= 2 and s[1] <= 4)
    
    """
    return a deep copy of the given board
    """
    @staticmethod
    def deep_copy_board(original_board):
        copy = Board()
        for square in original_board._board:
            copy.add_tile(original_board.get_tile_at(square), square, original_board._turn.get(square,-1))
        return copy
        
    def get_tile_at(self, s):
        return self._board.get(s, None)
    
    def get_piece_at(self, s):
        return self._board[s].get_piece()
    
    def is_square_free(self, s):
        return self.get_piece_at(s) == Piece.BLANK
    
    def all_specials_used(self):
        return len(self._specials_used) == 3
    
    def count_specials_used(self):
        return len(self._specials_used)
    
    """
    return all the (r,c) pairs of pieces adjacent to the given square
    if internal is true, it is limited to internal pieces
    if forward is true, only squares to the right or below are considered
    """
    def adjacents(self, s, internal=False, forward=False):
        directions = [(0,1),(1,0)]
        if not forward:
            directions += [(-1,0),(0,-1)]
        if internal:
            return [(s[0]+dr,s[1]+dc) for (dr,dc) in directions
                    if Board.square_internal(s[0]+dr, s[1]+dc)]
        else:
            return [(s[0]+dr,s[1]+dc) for (dr,dc) in directions
                if (s[0]+dr,s[1]+dc) in self._board]
      
    """
    return list of (square, side) pairs with all the adjacent squares
    where side is the side of this square
    """
    def adjacents_with_sides(self, s, internal=False, forward=False):
        adjacents = []
        for side in Side:
            oppS, _ = self.opposite_edge(s, side)
            if internal and Board.s_internal(oppS):
                adjacents += [(oppS, side)]
            if not internal and oppS in self._board:
                adjacents += [(oppS, side)]
        return adjacents
    
    @staticmethod
    def get_start_squares():
        return {(r,c) for r,c,t in HIGHWAY_START_POSITIONS + RAILWAY_START_POSITIONS}
    
    @staticmethod
    def square_internal(r,c):
        return r >= 0 and r < NUM_ROWS and c >= 0 and c < NUM_ROWS
    
    @staticmethod
    def s_internal(s):
        return Board.square_internal(s[0],s[1])
    
    
    
    ###################CLUSTERING LOGIC###########################
    """
    create a cluster for each of the squares on the board
    """       
    def _initialise_clusters(self):
        clusters = {}
        #iterate through each of the squares and create a new cluster for every square
        for s in self._board:
            tile = self.get_tile_at(s)
            #if the piece is an overpass, treat it as two separate tiles for clustering
            if tile.get_piece() == Piece.OVERPASS:
                railway_tile = Tile(Piece.OVERPASS_RAILWAY, tile.get_rotation())
                highway_tile = Tile(Piece.OVERPASS_HIGHWAY, tile.get_rotation())
                clusters[s] = [Cluster(s[0], s[1], railway_tile), Cluster(s[0], s[1], highway_tile)]
            else:
                clusters[s] = [Cluster(s[0], s[1], tile)] #this is a list of clusters to handle overpasses
        return clusters
      
    """
    process all non-start clusters by joining them together where there are connections
    """              
    def _process_clusters(self, clusters):
        #only reach up and left, this means that every bridge will be processed once
        #go through them in this ordering just to enforce a nice ordering rather than
        #the random nature of looping through a dictionary
        for row in range(-1, NUM_ROWS + 1):
            for col in range(-1, NUM_COLS + 1):
                #check there is actually a piece at this location, if not skip over it
                if self.get_tile_at((row,col)) == None:
                    continue
                
                #try and join with the cluster above - unless there is not one
                if self.get_tile_at((row-1,col)) != None:
                    #need to go through this list, there is almost certainly only one element - unless it's an overpass
                    for cluster in clusters[row,col]:
                        for cluster_above in clusters[row - 1,col]:
                            Cluster.try_join_clusters(cluster, cluster_above, Side.TOP)
                #try and join with the cluster to the left - unless we are in the left column
                if self.get_tile_at((row, col-1)) != None:
                    for cluster in clusters[row,col]:
                        for cluster_left in clusters[row,col - 1]:
                            Cluster.try_join_clusters(cluster, cluster_left, Side.LEFT)
     
    """
    get all the representative elements in the clusters. These are the top of each cluster
    and contain all information about the cluster
    """                       
    def _get_cluster_representatives(self, clusters):
        cluster_reps = []
        for row in range(-1, NUM_ROWS+1):
            for col in range(-1, NUM_COLS+1):
                if self.get_tile_at((row,col)) != None:
                    for cluster in clusters[row,col]:
                        if cluster.is_representative():
                            cluster_reps += [cluster]
        return cluster_reps
    
    """
    check for any illegal clusters that are detached from any start point, these are illegal
    raises ValueError for any illegal board configurations
    """
    def _check_for_illegal_clusters(self, cluster_reps):
        for cluster in cluster_reps:
            #an illegal cluster has no start points (or overpasses where a new cluster can be created)
            if (not cluster.is_blank_cluster() and cluster.get_start_count() == 0 
                and cluster.get_overpass_count() == 0):
                raise ValueError("Cluster has no start element -", cluster.get_cluster_tiles())
        
       
    """
    find all the clusters in the board, returns a list of clusters
    """
    def find_clusters(self):
        #first create a cluster for every square on the board
        clusters = self._initialise_clusters()
          
        #next process all the clusters, only reach up and left, since each pair only needs to be done once          
        self._process_clusters(clusters)

        #find all the representative elements of the clusters, these have parents that have themselves as parents
        cluster_reps = self._get_cluster_representatives(clusters)
        
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
    determine all the possible moves that could be made from here with a given dictionary of pieces and counts
    if include_specials is True, allow for special pieces if there remain available specials
    """
    def all_possible_moves(self, pieces_to_use, include_specials=True):
        if not self._clusters_up_to_date:
            self.find_clusters()
        
        #copy the pieces dictionary to a local dictionary to not change it
        pieces = dict(pieces_to_use)
        #if there is a special piece available, add one to the pieces dictionary
        if include_specials and not self.all_specials_used():
            pieces[Piece.SPECIAL] = 1
            
        #generate all the tile variations for all of them
        variations = {}
        for piece in pieces:
            if piece == Piece.SPECIAL:
                variations[piece] = []
                for special_piece in SPECIAL_PIECES:
                    if special_piece not in self._specials_used:
                        variations[piece] += Tile.get_variations(special_piece)
                        
            else:
                variations[piece] = Tile.get_variations(piece)
            
        #first things first, we definitely need to know where we can make moves, this has two components
        #it has the free squares and also all the connections
        free_squares = set(self._free_squares)
        edges = set()
        for cluster_rep in self._cluster_reps:
            if not cluster_rep.is_blank_cluster():
                for clusterEdge in cluster_rep.get_frontier():
                    edges.add(clusterEdge)

        #now set the recursive function in motion
        all_moves = set()
        self.possible_moves([], pieces, variations, edges, free_squares, all_moves, set())
        #return all the possible moves, as a list so it is quicker to iterate over
        return list(all_moves)
        
    """
    determines all the possible moves with the given pieces with the current set of edges to join to
    and free squares to place in, this is a recursive function
    visited considers the set of move sets that have already been considered
    """
    def possible_moves(self, move_list, pieces, variations, edges, free_squares, all_moves, visited):
        
        #only consider move combinations we have not seen before
        move_tuple = tuple(sorted(move_list))
        if move_tuple not in visited:
            base_case = True #determines whether we are at the base case (i.e if there are any pieces that can be played)
            for piece in pieces:
                #see if we have any more of this piece to play
                piece_count = pieces[piece]
                if piece_count > 0:
                    
                    #consider every possible place we could play this piece, it must be attached to some edge
                    for edge in edges:
                        newS, newSide = self.opposite_edge((edge.row, edge.col), edge.side)
                        #check that this opposite edge is a free square, so we could play there
                        if newS in free_squares:
                            #then we could play any variation of this piece there
                            for tile in variations[piece]:
                                #now we need to see if we can play this tile attaching to this edge
                                if tile.get_edge_type_on_side(newSide) == edge.edgeType:
                                    #now we need to have a think about the other edges of the tile we would place there
                                    #this could have a clash (meaning the piece cannot be played) or may need to have
                                    #some more edges added to the edges set before making a recursive call
                                    new_edges = []
                                    clash = False
                                    for side in Side:
                                        if side != newSide: #don't consider the same side we just considered
                                            #get the edge type that would be connecting here
                                            edgeType = tile.get_edge_type_on_side(side)
                                            #blanks do nothing, only consider non blanks
                                            if edgeType != EdgeType.B:
                                                #now get where this next connection would be
                                                oppS, oppSide = self.opposite_edge(newS, side)
                                                #now see what is there
                                                #first consider the case where we get a clash if we play this new piece here
                                                if ClusterEdge(oppS[0], oppS[1], oppSide, EdgeType.clash_type(edgeType)) in edges:
                                                    clash = True
                                                    break
                                                #the next case is if we have a free square on this edge, meaning that we
                                                #have a new edge to consider when placing the next piece
                                                #if there isn't a free square there, then whatever this end is it is 
                                                #hitting a dead end and does not need to be considered when making
                                                #the recursive call
                                                if oppS in free_squares:
                                                    new_edges.append(ClusterEdge(newS[0], newS[1], side, edgeType))
                                    
                                    #now if there wasn't a clash at all, we can play this piece and make a recursive call
                                    if not clash:
                                        #we need to fix up all the values getting called, this involves a lot of creation
                                        #as we are halfway through iterating a bunch of things and modifying them is a bad idea
                                        
                                        #however the move_list isn't being iterated over so we can happily modify that and undo it
                                        move_list.append((newS, tile)) #we are playing tile at the new square
                                        
                                        #create a new set of edges with this edge removed and the created edges added
                                        rec_edges = set(edges)
                                        rec_edges.remove(edge) #we have used this edge, but we have to add the new ones
                                        for new_edge in new_edges:
                                            rec_edges.add(new_edge) #we have all these new edges
                                            
                                        #create a new pieces dictionary with the updated value
                                        rec_pieces = dict(pieces)
                                        rec_pieces[piece] -= 1 #decrement the number of this piece we have left
                                        
                                        free_squares.remove(newS) #this is no longer a free square, not being iterated
                                        
                                        self.possible_moves(move_list, rec_pieces, variations, rec_edges, free_squares, all_moves, visited)
                                        
                                        #undo some of the changes
                                        free_squares.add(newS)
                                        move_list.pop()
                                    
                                        #we have made at least one recursive call, therefore this is not the base case
                                        base_case = False
            
  
            visited.add(move_tuple) #mark this move set as seen to not do this again
            
            #if this was the base case, then add this to the set of all moves
            if base_case:
                all_moves.add(tuple(sorted(move_list)))
    
    """
    brute force approach to finding the best move that can be made,
    tries every single move then finds the one with the highest score
    """
    def best_move(self, pieces):
        #generate all the possible moves
        all_moves = self.all_possible_moves(pieces)
        best_score = (0,)
        best_moves = None
        #then score all of these scenarios
        for moves_list in all_moves:
            new_score = self.score_moves(moves_list)
            if new_score > best_score:
                best_score = new_score
                best_moves = moves_list
        return best_score, best_moves

            
    """
    score the board if the moves in the given list are added to the board
    does not change the state of the board
    """
    def score_moves(self, moves_list):
        #first add all the tiles
        for s, tile in moves_list:
            self.add_tile(tile, s)
        #then score the board
        score = self.score()
        #next remove the newly added tiles to leave the board as it was
        for s, tile in moves_list:
            self.remove_tile(s)
        #then return the found score
        return score
    
    """
    get the score of the board as it lies
    """
    def score(self):
        if not self._clusters_up_to_date:
            self.find_clusters()
            
        centre_points = 0
        #first count the centre squares
        for row in range(2,5):
            for col in range(2,5):
                if self.get_piece_at((row,col)) != Piece.BLANK:
                    centre_points += 1
        
        joining_exits_points = 0
        #next score the cluster based points
        for cluster_rep in self._cluster_reps:
            #only consider clusters with pieces in them, not blank clusters
            if not cluster_rep.is_blank_cluster():
                #every non blank cluster has at least one start piece, an error was thrown
                #if they didn't since that is illegal, score points 
                joining_exits_points += 4*(max(cluster_rep.get_start_count() - 1, 0))
        
        #next determine the error count by finding every join that has a blank on one side and not the other   
        #only look right and down, since errors can only be internal      
        #while we are doing this, establish the connections for the longest path searches 
        #(connections is an adjacency list graph representation)
        railway_connections = {}
        highway_connections = {}
        errors = 0
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                if row != NUM_ROWS - 1:
                    topEdge = self.get_tile_at((row,col)).get_edge_type_on_side(Side.BOTTOM)
                    bottomEdge = self.get_tile_at((row+1,col)).get_edge_type_on_side(Side.TOP)
                    if (topEdge == EdgeType.R and bottomEdge == EdgeType.R):
                        self._add_connection((row,col), (row+1,col), railway_connections)
                    elif (topEdge == EdgeType.H and bottomEdge == EdgeType.H):
                        self._add_connection((row,col), (row+1,col), highway_connections)
                    #if they are not both blank there is an error, since we know the game is valid
                    elif not (topEdge == EdgeType.B and bottomEdge == EdgeType.B):
                        errors += 1
                if col != NUM_COLS - 1:
                    leftEdge = self.get_tile_at((row,col)).get_edge_type_on_side(Side.RIGHT)
                    rightEdge = self.get_tile_at((row,col+1)).get_edge_type_on_side(Side.LEFT)
                    if (leftEdge == EdgeType.R and rightEdge == EdgeType.R):
                        self._add_connection((row,col), (row,col+1), railway_connections)
                    elif (leftEdge == EdgeType.H and rightEdge == EdgeType.H):
                        self._add_connection((row,col), (row,col+1), highway_connections)
                    elif not (leftEdge == EdgeType.B and rightEdge == EdgeType.B):
                        errors += 1
                   
        #use DFS at each point to determine the longest paths, updating the overall longest paths
        longest_railway = 0
        longest_highway = 0
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                longest_railway = max(longest_railway, self._longest_path_dfs((row,col), railway_connections, set()))
                longest_highway = max(longest_highway, self._longest_path_dfs((row,col), highway_connections, set()))
    
        #consider the bonus point
        if joining_exits_points == 44:
            joining_exits_points += 1
            
        score = centre_points + joining_exits_points + longest_railway + longest_highway - errors
        return score, joining_exits_points, longest_railway, longest_highway, centre_points, -1*errors
    
    """
    add a connection to the connections dictionary in both directions.
    add end to the list of squares accessible from start and vice versa
    """
    def _add_connection(self, start, end, connections):
        #first check if they have any connections and establish empty lists if they are not
        if start not in connections:
            connections[start] = []
        if end not in connections:
            connections[end] = []
        #then append them both
        connections[start].append(end)
        connections[end].append(start)
        
    """
    perform a dfs with the given connections graph where the visited set cannot be revisited
    and returns the length of the longest path
    Do note that this won't work in the case of there being no length 2 paths in the whole
    game, but that isn't a useful case so it's just ignored
    """
    def _longest_path_dfs(self, square, connections, visited):
        #first check there is even a connection at this vertex
        if square not in connections:
            return 0
        #in case there are no connections, establish the max_depth as if this is the end
        max_depth = 1
        #add the current square to the visited set, and remove it after all recursive calls
        visited.add(square)
        #now do any visits
        for next_square in connections[square]:
            #only visit something if it's not already on the longest path
            if next_square not in visited:
                max_depth = max(max_depth, self._longest_path_dfs(next_square, connections, visited) + 1)
        
        #remove from the visited set once all recursive calls have been made
        visited.remove(square)        
        return max_depth
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
            
        if tile.get_piece() == Piece.OVERPASS_HIGHWAY or tile.get_piece() == Piece.OVERPASS_RAILWAY:
            self._overpass_count = 1
        else:
            self._overpass_count = 0
        
        #add all the edges of the cluster
        self._frontier = []
        if not self._blank_cluster:
            for side in Side:
                edgeType = tile.get_edge_type_on_side(side)
                if edgeType != EdgeType.B:
                    self._frontier += [ClusterEdge(row, col, side, edgeType)]
        
        #initialise the longest path tracking
        self._longest_paths = {}
        self._longest_paths[EdgeType.R] = {}
        self._longest_paths[EdgeType.H] = {}
        
        if not self._blank_cluster:
            for e in [EdgeType.R, EdgeType.H]:
                #first count how many railways or highways sides there are
                count = 0
                for side in Side:
                    if tile.get_edge_type_on_side(side) == e:
                        count += 1
                #next use the counts to generate all the paths
                if count > 1:
                    for side in Side:
                        for otherSide in Side:
                            if (tile.get_edge_type_on_side(side) == e and tile.get_edge_type_on_side(otherSide) == e
                                and side < otherSide):
                                #path of length 1 between any ends
                                self._longest_paths[e][((row, col, side), (row, col, otherSide))] = 1
                if count == 1:
                    for side in Side:
                        if tile.get_edge_type_on_side(side) == e:
                            if tile.get_piece() not in START_PIECES:
                                #longest path of length 1 to a dead end
                                self._longest_paths[e][(row, col, side), None] = 1
                            else:
                                #longest path of length 0 (start pieces don't count) to a dead end
                                self._longest_paths[e][(row, col, side), None] = 0

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
            representative1._overpass_count += representative2._overpass_count
        else:
            representative1._parent = representative2
            representative2._frontier += representative1._frontier
            representative2._cluster_tiles += representative1._cluster_tiles
            representative2._start_count += representative1._start_count
            representative2._overpass_count += representative1._overpass_count
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
        #blank from the cluster, because we won't ever be able to join to it, this is a -1 point
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
    
    def get_overpass_count(self):
        return self._overpass_count
    
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
class for a dice roll, a dice roll has a dictionary of pieces and a probability
"""
class DiceRoll:
    
    """
    Constructor.
    dice - dictionary mapping Pieces to number of occurrences
    probability - probability of this dice roll occuring, in [0,1]
    specials - the count of specials associated with this roll
    """
    def __init__(self, dice, probability, specials=1):
        self._dice = dice
        self._probability = probability
        self._specials = specials
    
    def get_dice(self):
        return self._dice
    
    def get_probability(self):
        return self._probability
    
    def specials(self):
        return self._specials

    
    """
    gets a list of the full distribution of dice rolls
    """
    @staticmethod
    def get_full_distribution():
        roll_counts = {}
        #consider all possible roll distributions
        for d1 in BASIC_PIECES:
            for d2 in BASIC_PIECES:
                for d3 in BASIC_PIECES:
                    for d4 in JUNCTION_PIECES:
                        #create a tuple for the roll
                        roll = tuple(sorted([d1,d2,d3,d4]))
                        roll_counts[roll] = roll_counts.get(roll, 0) + 1
        #now we have all the roll counts and their occurrences
        num_rolls = len(BASIC_PIECES)**3 * len(JUNCTION_PIECES)
        #sort these so that there is a determinstic ordering for comparing trials
        ordered_rolls = sorted([roll for roll in roll_counts])
        return [DiceRoll(Counter(roll), roll_counts[roll] / num_rolls)  for roll in ordered_rolls]
    
    def __repr__(self):
        return "({0}, {1})".format(self._dice, self._probability)

"""
create the board for the game shown in the rulebook
"""
def rulebook_game():
    board = Board()
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (0,1), 6)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,0), 3)
    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 3)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,2), 4)
    board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R180), (1,3), 4)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.I, flip=True), (1,4), 6)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (2,1), 2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (2,3), 5)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (2,5), 6)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,0), 2)
    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,1), 2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (3,2), 3)
    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R90), (3,5), 6)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,6), 4)
    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (4,2), 3)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R180, flip=False), (4,3), 4)
    board.add_tile(Tile(Piece.HIGHWAY_JUNCTION, Rotation.I), (4,4), 5)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,0), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (5,1), 1)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.I, flip=True), (5,2), 2)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (5,3), 4)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,6), 5)
    board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (6,1), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (6,3), 1)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (6,4), 5)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270, flip=False), (6,5), 5)
    return board

"""
the pieces available on the last turn of the default game, pass it the board for the specials
"""
def rulebook_dice_rolls():
    return [[DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
            Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 1)]]

if __name__ == "__main__":

    #board = rulebook_game()
    #board = Board()
    #board.fancy_board_print("turn-6.png")
    #reps = board.find_clusters()
    #print(board.score())
#    moves = board.all_possible_moves({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1,
#                                      Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1})
#    print(board.best_move({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1,
#                           Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}))
    
#    board = Board()
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R270), (1,0),1)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (0,0), 1)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (6,5), 1)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.I, flip=True), (0,1), 1)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (6,6), 2)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (5,6), 2)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,4), 2)
#    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (5,5), 2)
    
    #board.fancy_board_print()
#    a = board.all_possible_moves({Piece.STRAIGHT_STATION : 1, Piece.RAILWAY_CORNER : 1, 
#                             Piece.RAILWAY_T : 1, Piece.HIGHWAY_T : 1}, include_specials=False)
    
    board = Board()
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT,Rotation.R90), (0,2), 1)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (0,3), 1)
    board.add_tile(Tile(Piece.RAILWAY_CORNER,Rotation.I),(0,4),1)
    board.add_tile(Tile(Piece.CORNER_STATION,Rotation.R90,False),(0,1),1)
    board.add_tile(Tile(Piece.OVERPASS,Rotation.I,False),(1,6),2)
    board.add_tile(Tile(Piece.RAILWAY_T,Rotation.I,False),(1,5),2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER,Rotation.R90,False),(2,6),2)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R180), (0,6), 2)
    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (5,0), 3)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90, True), (6,0), 3)
    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (1,4), 3)
    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (6,1), 3)
    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (2,2), 4)
    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90, True), (3,2), 4)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (2,3), 4)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (2,4), 4)
    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R270), (3,3), 5)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (4,4), 5)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (6,3), 5)
    board.add_tile(Tile(Piece.CORNER_JUNCTION, Rotation.I), (5,3), 5)
    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (4,3), 5)
    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (5,6), 6)
    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (2,5), 6)
    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (5,4), 6)
    board.add_tile(Tile(Piece.THREE_H_JUNCTION, Rotation.I), (0,5), 6)
    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (3,5), 6)


    cp.fancy_board_print()

    #the perfect game
#    board = Board()
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R90), (0,1), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (0,2), 2)  
#    board.add_tile(Tile(Piece.CROSS_JUNCTION, Rotation.R90), (0,3), 2)
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (0,4), 1)  
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (0,5), 1)
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R180), (0,6), 1)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (1,0), 3)
#    board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 2)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (1,2), 2)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90), (1,6), 1)
#    board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (2,0), 3)
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (2,1), 3) 
#    board.add_tile(Tile(Piece.CORNER_JUNCTION, Rotation.R270), (2,2), 3)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (2,3), 3)
#    board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R270), (3,0), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (3,2), 4)
#    board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (3,3), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,4), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,5), 4)
#    board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R180), (3,6), 5) 
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R270), (4,0), 5)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (4,3), 5)
#    board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (4,6), 6)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (5,0), 6)
#    board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (5,1), 6)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (5,3), 7)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90), (5,6), 5)
#    board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (6,1), 6)
#    board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R90), (6,3), 7)
#    board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (6,4), 7)
#    board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270), (6,5), 7)
#    
#    board.fancy_board_print("the-perfect-game.png")