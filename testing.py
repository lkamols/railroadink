"""
file containing some tests for the constructed MILP
this was used to test whether additions broke the original functionality, was not developed too heavily
Author: Luke Kamols
"""

from board import Board, Tile, Piece, Rotation, DiceRoll, rulebook_game, rulebook_dice_rolls
from railroadInkSolver import RailroadInkSolver, RESULTS_FOLDER

import random
import math
import shutil
import csv
import os

TESTING_FOLDER = "testing"


"""
class for performing tests, not using a standard testing library because there needs to be
time tracking of each operation and aggregation of times done
"""        
class TestingSuite:
    
    def __init__(self):
        #all of the tests that have been written
        self._tests = [self.test_rulebook, 
                       self.test_no_special_play,
                       self.test_three_max,
                       self.test_four_loop,
                       self.test_six_loop,
                       self.test_rulebook_last_two,
                       self.test_rulebook_two_two
                       ]
    
    
    """
    run all of the tests
    """
    def run_all_tests(self, trials, seed=None):
        
        #if the testing folder exists, delete it, ensures there are no scraps if we change anything
        try:
            shutil.rmtree(RESULTS_FOLDER + "/" + TESTING_FOLDER)
        except FileNotFoundError:
            pass #if the folder wasn't there, we don't mind
        os.makedirs(RESULTS_FOLDER + "/" + TESTING_FOLDER)
        
        if seed != None:
            random.seed(seed)
        passes = 0
        test_results_path = "{0}/{1}/test-results.csv".format(RESULTS_FOLDER, TESTING_FOLDER)
        with open(test_results_path, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Test", "Passed", "Gave", "Gmin", "Gmax", "Aave", "Amin", "Amax"])
            #go through each of the test functions
            for test in self._tests:
                #run the test
                name, success, gurobi_times, absolute_times = test(trials, seed)
                #print some information about the trial
                print("\tOptimisation Times")
                print("\t\tave: {0:.2f} min: {1:.2f}, max: {2:.2f}".
                      format(gurobi_times[0], gurobi_times[1], gurobi_times[2]))
                print("\tTotal Times")
                print("\t\tave: {0:.2f} min: {1:.2f}, max: {2:.2f}".
                      format(absolute_times[0], absolute_times[1], absolute_times[2]))
                passes += (1 if success else 0)
                csv_writer.writerow([name, "PASSED" if success else "FAILED"] + gurobi_times + absolute_times)
            #print the overall results
            print("{0}/{1} TESTS PASSED".format(passes, len(self._tests)))
    
    """
    run a single test, returns whether it was a success, the average, min and max execution time of trials
    """
    def run_test(self, name, board, turn, dice_rolls, objective, expected_answer, trials, seed=None):
        
        #update the seed if we are doing a single test
        if seed != None:
            random.seed(seed)
        #create the solver object
        s = RailroadInkSolver(board, turn, dice_rolls, objective, path_loops="lazy")
        success = True #whether this run was successful
        #want the sum, min and max execution time, both in gurobi execution and total time
        gurobi_times = [0, float("inf"), 0]
        absolute_times = [0, float("inf"), 0]

        for i in range(trials):
            trial_seed = random.randrange(1000000)
            s.solve(folder="{0}/{1}/{1}-{2}".format(TESTING_FOLDER, name, trial_seed), printD="all", seed=trial_seed)
            #now that we have run the trial, check that the correct answer was reached
            if not math.isclose(s.get_result(), expected_answer, abs_tol=0.0001):
                print(name, "FAILED with seed", trial_seed, "expected:", expected_answer, "actual:", s.get_result())
                success = False
            #update the timing information
            self.update_times(s.get_gurobi_runtime(), gurobi_times)
            self.update_times(s.get_total_runtime(), absolute_times)
        print("PASSED" if success else "FAILED", name)    
        #update the sums to become averages
        gurobi_times[0] = round(gurobi_times[0]/trials, 2)
        absolute_times[0] = round(absolute_times[0]/trials, 2)
        
        return name, success, gurobi_times, absolute_times
    
    """
    update the times recorded in 'times', where 'times' is a 3 element array with [sum, min, max]
    and update these with the new time 'time'
    """
    def update_times(self, time, times):
        times[0] += time
        times[1] = min(times[1], time)
        times[2] = max(times[2], time)
    
    """
    run the rulebook game as a test
    """
    def test_rulebook(self, trials, seed=None):
        board = rulebook_game()
        dice_rolls = rulebook_dice_rolls()
        return self.run_test("Rulebook Test", board, 7, dice_rolls, "expected-score", 46, trials, seed)
    
    
    """
    tests when there is a choice to not play an available special
    also tests the bonus point allocation
    """
    def test_no_special_play(self, trials, seed=None):
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
        return self.run_test("No Special Played Test", board, 7, dice_rolls, "expected-score", 63, trials, seed)
    
    
    """
    tests playing three pieces in such a way that playing the 4th piece can be prevented
    """
    def test_three_max(self, trials, seed=None):
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
        return self.run_test("Three Pieces Played Max Test", board, 7, dice_rolls, "expected-score", 58, trials, seed)

        
    """
    test the removal of loops of size 4
    """
    def test_four_loop(self, trials, seed=None):
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
        return self.run_test("Size 4 Loop Test", board, 7, dice_rolls, "expected-score", 47, trials, seed)
        
    """
    test the removal of loops of size 6
    """
    def test_six_loop(self, trials, seed=None):
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
        return self.run_test("Size 6 Loop Test", board, 7, dice_rolls, "expected-score", 49, trials, seed)
    
    
    """
    test the final two moves of the rulebook game deterministically
    """
    def test_rulebook_last_two(self, trials, seed=None):
        board = Board()
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,0), 3)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 3)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,2), 4)
        board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R180), (1,3), 4)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (2,1), 2)
        board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (2,3), 5)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,0), 2)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,1), 2)
        board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (3,2), 3)
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
        
        dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
                                 Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
                      [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
                                 Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 1)]]
        return self.run_test("Two Turn Rulebook Test", board, 6, dice_rolls, "expected-score", 52, trials, seed)
    
    
    """
    tests the final two moves of the rulebook, with one option for turn 6 and two options for turn 7
    """
    def test_rulebook_two_two(self, trials, seed=None):
        board = Board()
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,0), 3)
        board.add_tile(Tile(Piece.OVERPASS, Rotation.I), (1,1), 3)
        board.add_tile(Tile(Piece.RAILWAY_STRAIGHT, Rotation.R90), (1,2), 4)
        board.add_tile(Tile(Piece.THREE_R_JUNCTION, Rotation.R180), (1,3), 4)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.I), (2,1), 2)
        board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R90), (2,3), 5)
        board.add_tile(Tile(Piece.HIGHWAY_STRAIGHT, Rotation.R90), (3,0), 2)
        board.add_tile(Tile(Piece.HIGHWAY_T, Rotation.I), (3,1), 2)
        board.add_tile(Tile(Piece.HIGHWAY_CORNER, Rotation.R270), (3,2), 3)
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
        
        dice_rolls = [[DiceRoll({Piece.HIGHWAY_STRAIGHT : 1, Piece.HIGHWAY_T : 1, 
                                 Piece.HIGHWAY_CORNER : 1, Piece.CORNER_STATION : 1}, 1)],
                      [DiceRoll({Piece.RAILWAY_STRAIGHT : 1, Piece.RAILWAY_CORNER : 1, 
                                 Piece.HIGHWAY_STRAIGHT : 1, Piece.OVERPASS : 1}, 0.6),
                       DiceRoll({Piece.HIGHWAY_T : 1, Piece.RAILWAY_T : 1,
                                 Piece.HIGHWAY_CORNER : 1, Piece.STRAIGHT_STATION : 1}, 0.4)]]    
    
        return self.run_test("Two Two Rulebook Test", board, 6, dice_rolls, "expected-score", 53.2, trials, seed)
        

if __name__ == "__main__":

    #create a testing suite and test all the problems with 3 different seeds
    t = TestingSuite()
    t.run_all_tests(3)