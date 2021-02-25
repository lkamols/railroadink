from enum import Enum
from dataclasses import dataclass
from PIL import Image

NUM_ROWS = 7
NUM_COLS = 7
NUM_SPECIALS = 3
NUM_STARTS = 12

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
        self._board = {}
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self._board[row,col] = Tile(Piece.BLANK, Rotation.I)
        self._initialise_start_tiles()
        self._solution_tiles = []
      
    """
    add a tile to the board
    """
    def add_tile(self, row, col, piece, rotation, flip=False):
        self._board[row,col] = Tile(piece, rotation, flip)
        
    """
    add a solution tile to the board, treated like a normal tile, but will be printed with an indicator
    """
    def add_solution_tile(self, row, col, tile):
        self._solution_tiles += [(row, col, tile)]
        
    """
    initialise all the start pieces
    """
    def _initialise_start_tiles(self):
        self._start_tiles = []
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
                    print(row,col)
                    piece_image = self._board[row,col].get_image()
                    im.paste(piece_image, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS, TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS))
        
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
    returns whether a square is one of the centre squares
    s is a square, i.e a (row, col) tuple
    """
    @staticmethod
    def is_centre_square(s):
        return (s[0] >= 2 and s[0] <= 4 and s[1] >= 2 and s[1] <= 4)
        
    def get_tile_at(self, s):
        return self._board[s]
    
    def get_piece_at(self, s):
        return self._board[s].get_piece()
    
    def is_square_free(self, s):
        return self.get_piece_at(s) == Piece.BLANK
    
    @staticmethod
    def get_start_squares():
        return {(r,c) for r,c,t in HIGHWAY_START_POSITIONS + RAILWAY_START_POSITIONS}
    

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
    return {Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
            Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}

if __name__ == "__main__":

    board = rulebook_game()
    board.fancy_board_print()