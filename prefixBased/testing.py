

import unittest
import time
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
        
        
class TestingSuite:
    
    """
    run a single test, returns whether it was a success, the average, min and max execution time of trials
    """
    @staticmethod
    def run_test(num, board, turn, dice_rolls, objective, expected_answer, trials, seed=None):
        #update the seed if we are doing a single test
        if seed != None:
            random.seed(seed)
        #create the solver object
        s = RailroadInkSolver(board, turn, dice_rolls, objective)
        success = True #whether this run was successful
        #want the max, min and average execution time
        time_min = float("inf")
        time_max = 0
        time_sum = 0
        for i in range(trials):
            trial_seed = random.random()
            #run the test, wrapped in a timer
            trial_start = time.time()
            run_ans = s.solve(seed=trial_seed)
            trial_time = time.time() - trial_start
            #now that we have run the trial, check that the correct answer was reached
            if run_ans != expected_answer:
                print("FAIL, test", num, "failed with seed", trial_seed, "expected:", expected_answer, "actual:", run_ans)
                success = False
            #update the timing information
            time_min = min(time_min, trial_time)
            time_max = max(time_max, trial_time)
            time_sum += trial_time
        print("Test", num, "PASSED" if success else "FAILED")        
        return success, time_sum/trials, time_min, time_max
    
    @staticmethod
    def test_rulebook(trials, seed=None):
        board = rulebook_game()
        dice_rolls = rulebook_dice_rolls()
        return TestingSuite.run_test(1, board, 7, dice_rolls, "expected-score", 46, trials, seed)
        

if __name__ == "__main__":
    #unittest.main(exit=False)
    
#    tester = TestSolver()
#    tester.test_six_loop()
    print(TestingSuite.test_rulebook(4))