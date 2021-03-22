

import unittest

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
        
        
if __name__ == "__main__":
    unittest.main()