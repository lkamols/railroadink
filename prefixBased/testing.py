

import unittest
from board import *
from railroadInkSolver import *

"""
Test suite for the Railroad Ink solver
"""
class TestSolver(unittest.TestCase):
    
    def test_rulebook(self):
        board = rulebook_game()
        dice_rolls = rulebook_dice_rolls()
        s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
        result = s.solve()
        self.assertEqual(result, 46)
        
    """
    tests when there is a choice to not play an available special
    also tests the bonus point allocation
    """
    def test_no_special_play(self):
        board = Board()
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,6), 1)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (1,6),1)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (2,6),1)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R270), (0,5),1)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90), (1,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,4),2)
        board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (0,1),3)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.R90), (0,2),3)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (0,3),3)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (1,0),3)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (2,0),4)
        board.add_tile(Tile(Piece.CROSS_JUNCTION, Rotation.R90), (3,0),4)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (5,0), 4)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (4,0), 4)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270), (5,1), 4)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (6,3), 5)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (6,2), 5)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R90), (6,1), 5)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (5,6), 5)
        board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R270), (6,6), 5)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R180), (6,5), 6)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (6,4), 6)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.R180), (5,3), 6)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,1), 6)
        dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 2, Piece.HIGHWAY_T : 1, 
            Piece.STRAIGHT_STATION : 1}, 1)]]
        s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
        result = s.solve()
        self.assertEqual(result, 63)
        
    """
    tests playing three pieces in such a way that playing the 4th piece can be prevented
    """
    def test_three_max(self):
        board = Board()
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,6), 1)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (1,6),1)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (2,6),1)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (0,5),1)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90), (1,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,4),2)
        board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (0,1),3)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.R90), (0,2),3)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.I), (0,3),3)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (1,0),3)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (2,0),4)
        board.add_tile(Tile(Piece.CROSS_JUNCTION, Rotation.R90), (3,0),4)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (5,0), 4)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (4,0), 4)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270), (5,1), 4)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (6,3), 5)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (6,2), 5)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R90), (6,1), 5)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (5,6), 5)
        board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R270), (6,6), 5)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R180), (6,5), 6)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (6,4), 6)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.R180), (5,3), 6)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,1), 6)
        dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 2, Piece.HIGHWAY_T : 1, 
            Piece.OVERPASS : 1}, 1)]]
        s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
        result = s.solve()
        self.assertEqual(result, 58)
        
    """
    test the removal of loops of size 4
    """
    def test_four_loop(self):
        board = Board()
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,6), 1)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (1,6),1)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (2,6),1)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (0,5),1)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90), (1,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,4),2)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R270), (0,3),3)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (3,2),3)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,3),3)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (1,0),3)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (2,0),4)
        board.add_tile(Tile(Piece.CROSS_JUNCTION, Rotation.R90), (3,0),4)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (5,0), 4)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (4,0), 4)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270), (5,1), 4)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (6,3), 5)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (6,2), 5)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R90), (6,1), 5)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (5,6), 5)
        board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R270), (6,6), 5)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (0,2), 6)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R90), (1,2), 6)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.I), (1,3), 6)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,1), 6)
        dice_rolls = [[DiceRoll({Piece.RAILWAY_CORNER : 3, Piece.OVERPASS : 1}, 1)]]
        s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
        result = s.solve()
        self.assertEqual(result, 47)
        
    """
    test the removal of loops of size 6
    """
    def test_six_loop(self):
        board = Board()
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,6), 1)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R180), (1,6),1)
        board.add_tile(Tile(Piece.STRAIGHT_STATION, Rotation.I), (2,6),1)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (0,5),1)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R90), (1,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,5),2)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,4),2)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.R270), (0,3),3)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (3,2),3)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,3),3)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R270), (1,0),3)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (2,0),4)
        board.add_tile(Tile(Piece.CROSS_JUNCTION, Rotation.R90), (3,0),4)
        board.add_tile(Tile(Piece.RAILWAY_T, Rotation.I), (5,0), 4)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (4,0), 4)
        board.add_tile(Tile(Piece.CORNER_STATION, Rotation.R270), (5,1), 4)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.R90), (6,3), 5)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (6,2), 5)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.R90), (6,1), 5)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (5,6), 5)
        board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R270), (6,6), 5)
        board.add_tile(Tile(Piece.RAILWAY_CORNER, Rotation.R180), (0,2), 6)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (1,2), 6)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.I), (1,3), 6)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,1), 6)
        dice_rolls = [[DiceRoll({Piece.RAILWAY_CORNER : 3, Piece.OVERPASS : 1}, 1)]]
        s = RailroadInkSolver(board, 7, dice_rolls, "expected-score")
        result = s.solve()
        self.assertEqual(result, 49)
        
        
if __name__ == "__main__":
    #unittest.main(exit=False)
    
    tester = TestSolver()
    tester.test_six_loop()