from enum import Enum

from PIL import Image

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
    
class Orientation(Enum):
    DEFAULT = 0
    #turns considered clockwise
    TURN_90 = 1
    TURN_180 = 2
    TURN_270 = 3

class Tile:
    
    #map of all the tiles in their default orientation
    tile_map = {
        Piece.RAILWAY_CORNER: (Edge.R, Edge.B, Edge.B, Edge.R, False),
        Piece.RAILWAY_T: (Edge.R, Edge.R, Edge.B, Edge.R, False),
        Piece.RAILWAY_STRAIGHT: (Edge.R, Edge.B, Edge.R, Edge.B, False),
        Piece.HIGHWAY_CORNER: (Edge.H, Edge.B, Edge.B, Edge.H, False),
        Piece.HIGHWAY_T: (Edge.H, Edge.H, Edge.B, Edge.H, False),
        Piece.HIGHWAY_STRAIGHT: (Edge.H, Edge.B, Edge.H, Edge.B, False),
        Piece.OVERPASS: (Edge.H, Edge.R, Edge.H, Edge.R, True),
        Piece.STRAIGHT_STATION: (Edge.R, Edge.B, Edge.H, Edge.B, False),
        Piece.CORNER_STATION: (Edge.R, Edge.B, Edge.B, Edge.H, False),
        Piece.THREE_H_JUNCTION: (Edge.H, Edge.H, Edge.R, Edge.H, False),
        Piece.THREE_R_JUNCTION: (Edge.H, Edge.R, Edge.R, Edge.R, False),
        Piece.HIGHWAY_JUNCTION: (Edge.H, Edge.H, Edge.H, Edge.H, False),
        Piece.RAILWAY_JUNCTION: (Edge.R, Edge.R, Edge.R, Edge.R, False),
        Piece.CORNER_JUNCTION: (Edge.H, Edge.R, Edge.R, Edge.H, False),
        Piece.CROSS_JUNCTION: (Edge.H, Edge.R, Edge.H, Edge.R, False),         
        }
    
    tile_pics = {
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
        self.piece = piece
        self.orientation = orientation
        #load in all the left, right, down, up and overpass values
        #load these upon creation because they will be accessed multiple times
        self.up, self.right, self.down, self.left, self.overpass = self.tile_map[piece]
        self.rotate(orientation)
        
    """
    rotate the tile to the given orientation, assumes in default orientation
    """
    def rotate(self, orientation):
        #rotate to the given orientation, enum values are the number of rotations required
        for rotations in range(orientation.value):
            #change all the assignments in the same line, handles the required temporary variables
            self.up, self.right, self.down, self.left = self.left, self.up, self.right, self.down
         
    """
    get the image associated with this piece and orientation, scaled to fit on the board image
    """
    def get_image(self):
        #get the correct image
        piece_image = Image.open(PHOTOS_FOLDER + self.tile_pics[self.piece])
        #resize the image
        piece_image = piece_image.resize([BOARD_WIDTH//NUM_COLS, BOARD_HEIGHT//NUM_ROWS], Image.ANTIALIAS)
        #rotate the image
        if self.orientation == Orientation.TURN_90:
            piece_image.rotate(90)
        elif self.orientation == Orientation.TURN_180:
            piece_image.rotate(180)
        elif self.orientation == Orientation.TURN_270:
            piece_image.rotate(270)
        return piece_image
    
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
        return "({0},{1},{2},{3},{4},{5},{6})".format(self.piece.name, self.orientation.name, self.up.name, self.right.name, self.down.name, self.left.name, "T" if self.overpass else "F")
    
class Board:
    
    def __init__(self):
        #create an empty board with no tiles in it yet
        self.board = [[None]*NUM_COLS for i in range(NUM_ROWS)]
        
    def add_tile(self, row, col, piece, orientation):
        self.board[row][col] = Tile(piece, orientation)
    
        
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
                if self.board[row][col] != None:
                    piece_image = self.board[row][col].get_image()
                    im.paste(piece_image, (LEFT_OFFSET + BOARD_WIDTH * col // NUM_COLS, TOP_OFFSET + BOARD_HEIGHT * row // NUM_ROWS))
        
        #now display the image, depending on if a file is given
        if file == None:
            im.show()
        else:
            im.save(file)

    

       

if __name__ == "__main__":
    
    print(Tile(Piece.CORNER_JUNCTION, Orientation.DEFAULT))
    print(Tile(Piece.CORNER_JUNCTION, Orientation.TURN_90))
    print(Tile(Piece.CORNER_JUNCTION, Orientation.TURN_180))
    print(Tile(Piece.CORNER_JUNCTION, Orientation.TURN_270))

    board = Board()
    board.add_tile(2,3, Piece.RAILWAY_CORNER, Orientation.DEFAULT)
    board.fancy_board_print()


    
    
    
    
    
    
"""
    #create a dictionary with all the tiles, this is a constant across all boards, this is just data
    tiles = {
        Piece.RAILWAY_CORNER: generate_tile_rotations(Tile(Edge.R, Edge.B, Edge.B, Edge.R), 4),
        Piece.RAILWAY_T: generate_tile_rotations(Tile(Edge.R, Edge.R, Edge.B, Edge.R), 4),
        Piece.RAILWAY_STRAIGHT: generate_tile_rotations(Tile(Edge.R, Edge.B, Edge.R, Edge.B), 2),
        Piece.HIGHWAY_CORNER: generate_tile_rotations(Tile(Edge.H, Edge.B, Edge.B, Edge.H), 4),
        Piece.HIGHWAY_T: generate_tile_rotations(Tile(Edge.H, Edge.H, Edge.B, Edge.H), 4),
        Piece.HIGHWAY_STRAIGHT: generate_tile_rotations(Tile(Edge.H, Edge.B, Edge.H, Edge.B), 2),
        Piece.OVERPASS: generate_tile_rotations(Tile(Edge.H, Edge.R, Edge.H, Edge.R, overpass=True), 2),
        Piece.STRAIGHT_STATION: generate_tile_rotations(Tile(Edge.R, Edge.B, Edge.H, Edge.B), 2),
        Piece.CORNER_STATION: generate_tile_rotations(Tile(Edge.R, Edge.B, Edge.B, Edge.H), 4),
        Piece.THREE_H_JUNCTION: generate_tile_rotations(Tile(Edge.H, Edge.H, Edge.R, Edge.H), 4),
        Piece.THREE_R_JUNCTION: generate_tile_rotations(Tile(Edge.H, Edge.R, Edge.R, Edge.R), 4),
        Piece.HIGHWAY_JUNCTION: generate_tile_rotations(Tile(Edge.H, Edge.H, Edge.H, Edge.H), 1),
        Piece.RAILWAY_JUNCTION: generate_tile_rotations(Tile(Edge.R, Edge.R, Edge.R, Edge.R), 1),
        Piece.CORNER_JUNCTION: generate_tile_rotations(Tile(Edge.H, Edge.R, Edge.R, Edge.H), 4),
        Piece.CROSS_JUNCTION: generate_tile_rotations(Tile(Edge.H, Edge.R, Edge.H, Edge.R), 2)
    }"""