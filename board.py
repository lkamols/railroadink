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
    #start pieces (the edge tiles)
    START_RAILWAY = 15
    START_HIGHWAY = 16
    
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
    
#start locations of all the highways and railways
highway_start_positions = [(-1, 1, Orientation.TURN_180), (-1, 5, Orientation.TURN_180),
                           (3, -1, Orientation.TURN_90), (3, NUM_COLS, Orientation.TURN_270),
                           (NUM_ROWS, 1, Orientation.DEFAULT), (NUM_ROWS, 5, Orientation.DEFAULT)]
railway_start_positions = [(-1, 3, Orientation.TURN_180), (NUM_ROWS, 3, Orientation.DEFAULT),
                           (1, -1, Orientation.TURN_90), (5, -1, Orientation.TURN_90),
                           (1, NUM_COLS, Orientation.TURN_270), (5, NUM_COLS, Orientation.TURN_270)]

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
        Piece.START_RAILWAY: (Edge.R, Edge.B, Edge.B, Edge.B, False),
        Piece.START_HIGHWAY: (Edge.H, Edge.B, Edge.B, Edge.B, False)
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
        self._dirs = {}
        self._dirs[Side.TOP], self._dirs[Side.RIGHT], self._dirs[Side.BOTTOM], \
                self._dirs[Side.LEFT], self.overpass = self.tile_map[piece]
        self.rotate(orientation)
        
    """
    rotate the tile to the given orientation, assumes in default orientation
    """
    def rotate(self, orientation):
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
    get the edge type associated with one of the directions
    """
    def get_edge_type_on_side(self, side):
        return self._dirs[side]
    
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
        return "({0},{1},{2},{3},{4},{5},{6})".format(self.piece.name, self.orientation.name, 
               self._dirs[Side.TOP].name, self._dirs[Side.RIGHT].name, self._dirs[Side.BOTTOM].name,
               self._dirs[Side.LEFT].name, "T" if self.overpass else "F")
    
class Board:
    
    def __init__(self):
        #create an empty board with no tiles in it yet
        self.board = [[None]*NUM_COLS for i in range(NUM_ROWS)]
        self.initialise_start_tiles()
      
    """
    add a tile to the board
    """
    def add_tile(self, row, col, piece, orientation):
        self.board[row][col] = Tile(piece, orientation)
        
    """
    add a start tile to the board, these are the pieces around the edge
    """
    def add_start_tile(self, row, col, piece, orientation):
        self.start_pieces += [(row, col, Tile(piece, orientation))]
        
    """
    initialise all the start pieces
    """
    def initialise_start_tiles(self):
        self.start_pieces = []
        for row, col, orientation in railway_start_positions:
            self.add_start_tile(row, col, Piece.START_RAILWAY, orientation)
        for row, col, orientation in highway_start_positions:
            self.add_start_tile(row, col, Piece.START_HIGHWAY, orientation)
        
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
        self.parent = None
        self.tile = tile
        self.row = row
        self.col = col
        self.blank_cluster = (tile == None) #whether this cluster is a blank cluster or a tiled cluster
        
    #def join
            
       

if __name__ == "__main__":

    board = Board()
    board.add_tile(2,3, Piece.RAILWAY_CORNER, Orientation.DEFAULT)
    board.fancy_board_print()

