from railroadInkSolver import RailroadInkSolver, RESULTS_FOLDER, create_empty_folder, DECISIONS_CSV
from board import Board, Tile, Piece, Rotation, DiceRoll, BASIC_PIECES, JUNCTION_PIECES
import random
import csv
import json
import math
import numpy as np
import time
import func_timeout
import os.path
from os import path

TURNS = 7
PHOTO_FILENAME = "solution.png"

SCORE_CSV = "score.csv"
INFO_CSV = "info.csv"
MOVES_CSV = "moves.csv"
EVALUATE_CSV = "evaluation.csv"
COMPARISON_CSV = "comparison.csv"
ERROR_FILE = "MISMATCH.txt"

BASE_CONFIG_NAME = "INITIAL"

PLAYER_FOLDER = "players"
BOARDS_FOLDER = "boards"

REMOVE_FROM_KWARGS = ["rolls", "solvetime", "runtime", "cache"]

"""
Arguments in player files
All arguments to the RailroadInkSolver init function
rolls - defines the types of rolls to consider
runtime/solvetime - the total runtime and the portion of this allocated to solving the model
        for the case that we are using the solve/evaluate approach for determining the best move
"""

"""
generates the rolls for a single game of Railroad Ink
this would be refactored to be a loop over the below function
but it would change how the rolls are generated so can't be changed
"""
def generate_game_rolls(game_seed):
    random.seed(game_seed) #overrides the set seed for backwards compatability
    rolls = []
    for turn in range(TURNS):
        counts = {} #the counts of each dice rolled
        dice = BASIC_PIECES #start with the basic pieces dice
        #roll 4 dice and update the entries for all of them
        for num in range(4):
            #if we are at the last roll, change the dice to be the junction dice
            if num == 3:
                dice = JUNCTION_PIECES
            
            #roll the dice as a random sample
            roll = random.sample(dice, 1)[0]
            #increase the count of this roll
            counts[roll] = counts.get(roll, 0) + 1
        #add this count to the rolls
        rolls.append(counts)
    return rolls

"""
generate a roll for a single turn of Railroad Ink
"""
def generate_game_roll():
    counts = {} #the counts of each dice rolled
    dice = BASIC_PIECES #start with the basic pieces dice
    #roll 4 dice and update the entries for all of them
    for num in range(4):
        #if we are at the last roll, change the dice to be the junction dice
        if num == 3:
            dice = JUNCTION_PIECES
        
        #roll the dice as a random sample
        roll = random.sample(dice, 1)[0]
        #increase the count of this roll
        counts[roll] = counts.get(roll, 0) + 1
    return counts


"""
generates a full scenario of dice rolls given the rolls argument in the supplied file
"""
def generate_scenario(start_roll, rolls):
    dice_rolls = [[DiceRoll(start_roll, 1)]] #start with this dice roll
    for arg in rolls:
        #check if we have an integer (i.e randomly generate this tier with the given number of arguments)
        this_turn = []
        if isinstance(arg, int):
            
            #add rolls for each of the args
            #this does allow repeats, but they are very rare and in a lot of ways, not an issue
            for i in range(arg):
                this_turn.append(DiceRoll(generate_game_roll(),1.0/arg))
            
        else:
            #if it wasn't an integer, then it is an argument with a scenario
            for roll in arg:
                #need to change this dictionary
                pieces = {Piece[p] : roll[0][p] for p in roll[0]} #convert strings to Pieces
                probability = roll[1]
                #check for if there was a special argument
                if len(roll) == 3:
                    specials = roll[2]
                else:
                    specials = 1
                this_turn.append(DiceRoll(pieces, probability, specials))
                
        dice_rolls.append(this_turn)
    return dice_rolls            

"""
class for a player of the game, has the ability to run a full game
simulation, given some configuration file
"""
class RailroadInkPlayer:
    
    """
    Constructor.
    Creates the given player from the player file by that name which defines how the player will play
    Creates a game with the given game_seed
    scenario defines the board type that is being run, or "full-game" for a full game
    """
    def __init__(self, player, game_seed, scenario="full-game"):
        #work out the folder that will be saved to 
        #(the call to RailroadInkSolver prepends the root folder, so have one version without the root)
        self._call_folder = "{0}/{1}/Seed-{2}".format(scenario, player, game_seed)
        self._folder = "{0}/{1}".format(RESULTS_FOLDER, self._call_folder)
        
        #read in the config file which is stored as a json
        player_file_location = "{0}/{1}.txt".format(PLAYER_FOLDER, player)
        with open(player_file_location) as jsonFile:
            self._config = json.load(jsonFile)
        #convert the base arguments into a dictionary, this dictionary can be updated on any turn
        #if this is empty, leave kwargs empty (although this will throw an error on the call)
        self._kwargs = {}
        for kw in self._config.get(BASE_CONFIG_NAME, {}):
            self._kwargs[kw] = self._config[BASE_CONFIG_NAME][kw] 
            
        self._game_seed = game_seed
        random.seed(game_seed) #seed the game
        self._scenario = scenario
      
    """
    read from a file a set of moves
    returns a list of moves as (tile, square, turn) tuples
    """
    def _moves_from_file(self, file):
        moves = []
        with open(folder, newline='') as movescsv:
            csvreader = csv.reader(movescsv, delimiter=",")
            for entry in csvreader:
                #do a quick check that the row being read is an information row
                if "Piece." in entry[0]:
                    #first unpack
                    piece = Piece[entry[0].split(".")[1]]
                    rotation = Rotation[entry[1].split(".")[1]]
                    flip = entry[2] == "True"
                    row = int(entry[3])
                    col = int(entry[4])
                    turn = int(entry[5])
                    moves.append((Tile(piece, rotation, flip), (row,col), turn))
        return moves
    
    """
    using the given scenario and game-seed, find the corresponding board file and load in the moves from it
    these are the starting moves
    returns the moves made, and the turn of the current move
    """
    def _get_starting_moves(self):
        file = f"{BOARDS_FOLDER}/{self._scenario}/board{self._game_seed}.csv"
        moves = self._moves_from_file(file)
        latest_turn = max(move[2] for move in moves) + 1
        return moves, latest_turn #the last turn + 1 is the current turn
    
    """
    if multiple solutions were found, compare them to find which is the best
    """
    def _compare_moves(self, board, s, turn, print_output):
        #now we need to evaluate these different solutions
        solns = s.get_multiple_solutions()
        solution_count = len(solns)
        move_results = [] #track the results of all of the different moves
        for soln in solns:
            #a solution is just a list of moves, need to update the board for each one
            for tile, square in soln:
                board.add_tile(tile, square, turn)
            #now using the new board, evaluate it by running all 168 scenarios
            move_results.append(self._evaluate_scenario(board, turn, print_output))
            #clear the board
            for tile, square in soln:
                board.remove_tile(square)
        win_probs = [0] * solution_count #all the candidates start with a win prob of 0
        #now go through each of the games and determine the winner and alter the win probabilities
        for game_index in range(len(self._all_rolls)):
            winning_score = max(move_results[move][game_index] for move in range(solution_count))
            for move in range(solution_count):
                if math.isclose(move_results[move][game_index], winning_score):
                    win_probs[move] += self._all_rolls[game_index].get_probability()
        #determine the move which wins most often
        best_move = np.argmax(win_probs)
        self._evaluate_csv(move_results[best_move])
        #do some printing of the data used to get here (for sanity checks)
        self._comparison_csv(move_results)
        return solns[best_move] #return the moves made in the best scenario
    
    """
    runs as many evaluations as possible with the remaining time, then evaluates the solutions 
    to determine which is best
    """
    def _timed_compare_moves(self, board, s, turn, print_output, runtime, start_time):
        #get the solutions which have been found
        solns = s.get_multiple_solutions()
        print("1st", solns)
        move_results = []
        for soln in solns:
            for tile, square in soln:
                board.add_tile(tile, square, turn)
            #now try to run the function with a timeout
            try:
                time_remaining = runtime - (time.time() - start_time) #how long is left
                #run the function with a timeout
                #this may alter the board state, so pass a deep copy of the board
                board_copy = Board.deep_copy_board(board)
                scenario_results = func_timeout.func_timeout(time_remaining, self._evaluate_scenario, args=(board_copy, turn, print_output))
                move_results.append(scenario_results)
            except func_timeout.FunctionTimedOut:
                #this run timed out, don't add any moves for this one and don't explore any more options
                #remove the squares
                for tile, square in soln:
                    board.remove_tile(square)
                break
            #remove the squares
            for tile, square in soln:
                board.remove_tile(square)
        #now that we are here, we have evaluated as many solutions as possible in the given time
        solution_count = len(move_results)
        win_probs = [0] * solution_count #all the candidates start with a win prob of 0
        #now go through each of the games and determine the winner and alter the win probabilities
        for game_index in range(len(self._all_rolls)):
            winning_score = max(move_results[move][game_index] for move in range(solution_count))
            for move in range(solution_count):
                if math.isclose(move_results[move][game_index], winning_score):
                    win_probs[move] += self._all_rolls[game_index].get_probability()
        #determine the move which wins most often
        print("2nd", solns)
        best_move = np.argmax(win_probs)
        self._evaluate_csv(move_results[best_move])
        #do some printing of the data used to get here (for sanity checks)
        self._comparison_csv(move_results)
        print("best move", best_move)
        print("best move moves", solns[best_move])
        return solns[best_move] #return the moves made in the best scenario        
    
    """
    solves for the move to make given a board, updates the moves_made list
    board - board before this turn
    moves_made - moves made up to this turn
    turn_dice - the dice rolled for this turn
    turn - the number of this turn
    """
    def _solve_turn(self, board, moves_made, turn_dice, turn, folder, print_output):
        #determine the dice_rolls to use
        dice_rolls = self._get_dice_rolls(turn_dice)
        
        #strip the 'rolls' information from the kwargs to pass them along
        kwargs = dict(self._kwargs)
        if "rolls" in kwargs:
            kwargs.pop("rolls")
        if kwargs.get("solvetime", 0) > 0:
            kwargs["timeouts"] = [kwargs["solvetime"]] * 7 #set the timeout to be the solvetime
            kwargs["solution_count"] = (kwargs["runtime"] // (8*60)) + 1 #work out how many max solutions to take
            start_time = time.time() #record the time we are starting everything
            
        for arg in REMOVE_FROM_KWARGS:
            if arg in kwargs:
                kwargs.pop(arg)
                
        print("BEFORE SOLVE")
        for r in range(7):
            for c in range(7):
                print(r, c, board.get_piece_at((r,c)))
        
        #run the game
        s = RailroadInkSolver(board, turn, dice_rolls, **kwargs)
        s.solve(folder=folder, print_output=print_output)
        
        print("AFTER SOLVE")
        for r in range(7):
            for c in range(7):
                print(r, c, board.get_piece_at((r,c)))
        
        #now check for if multiple solutions were generated and if so evaluate them
        if self._kwargs.get("solution_count", 1) > 1:
            moves = self._compare_moves(board, s, turn, print_output)
        elif self._kwargs.get("solvetime", 0) > 0:
            #we have done a solve, now we need to evaluate as many moves as possible with the remaining time
            moves = self._timed_compare_moves(board, s, turn, print_output, self._kwargs["runtime"], start_time)
        else:    
            #unpack the moves that were made and add them to moves_made
            moves = s.get_moves_made()[(0,)]
            
        #add the selected moves
        for tile, square in moves:
            board.add_tile(tile, square, turn)
            moves_made.append((tile, square, turn))
        return s
    
    """
    plays a single turn of Railroad Ink with the given player, board from the given scenario/board file
    and moves generated with given seed
    """
    def play_turn(self, print_pictures=False, print_output=False):
        #start by determining the moves with the given scenario and what turn we are up to
        moves_made, turn = self._get_starting_moves()
        #then load these into a board
        board = Board()
        for move in moves_made:
            board.add_tile(move[0], move[1], move[2])
        #then generate the roll 
        turn_dice = generate_game_roll()
        #determine how the player is supposed to make decisions at this turn by updating the kwargs
        #at each turn up until now
        for i in range(1, turn + 1):
            self._update_kwargs_dict(i)
       
        #actually solve the turn
        self._solve_turn(board, moves_made, turn_dice, turn, self._call_folder, print_output)         
            
        if print_pictures:
            board.fancy_board_print(file="{0}/{1}".format(self._folder, PHOTO_FILENAME))     
            
        #make a csv for the moves made
        self._make_moves_csv(moves_made)
        
        #save the board to the state, just for use in the evaluate_turn function
        self._board = board
        self._turn = turn
       
    """
    given a completed turn, determine the scores for each of the 168 possible dice rolls for the next turn
    """    
    def _evaluate_scenario(self, board, turn_played, print_output):
        turn = turn_played + 1
        self._update_kwargs_dict(turn) #update the player decision making
        
        #then generate all the possible different rolls that could occur for the turn after
        #ensure this is only done once to avoid a lot of recalculation
        if not hasattr(self, "_all_rolls"):
            self._all_rolls = DiceRoll.get_full_distribution()
        
        results = []
        for dice_roll in self._all_rolls:
            #determine the scenario tree for this solver
            dice_rolls  = self._get_dice_rolls(dice_roll.get_dice())
            
            #strip the 'rolls' information from the kwargs to pass them along
            kwargs = dict(self._kwargs)
            for arg in REMOVE_FROM_KWARGS:
                if arg in kwargs:
                    kwargs.pop(arg)
                
            s = RailroadInkSolver(board, turn, dice_rolls, **kwargs)
            s.solve(folder=None, print_output=print_output)
            results.append(round(s.get_result(),2))
        return results

    """
    take a turn, then evaluate it with the 168 different possible dice rolls, using the next
    turn of the given player
    """
    def evaluate_turn(self, print_pictures=False, print_output=False):
        self.play_turn(print_pictures, print_output) #first play the turn
        if self._kwargs.get("solution_count", 1) > 1 or self._kwargs.get("solvetime", None) != None:
            return #evaluation was already done
        results = self._evaluate_scenario(self._board, self._turn, print_output)
        self._evaluate_csv(results)
        
    """
    check if an existing calculation has been done for this turn, if so update the
    times and moves_made lists with the results
    returns the result if there was one, -1 otherwise
    """
    def _check_for_existing_calculation(self, turn_folder, turn, times, moves_made):
        #check if we have already calculated this turn and if so, don't redo it
        if path.isfile(f"{RESULTS_FOLDER}/{turn_folder}/{INFO_CSV}"):
            #read in the time taken and result from the infocsv
            with open(f"{RESULTS_FOLDER}/{turn_folder}/{INFO_CSV}", newline='') as infocsv:
                csvreader = csv.reader(infocsv, delimiter=",")
                for entry in csvreader:
                    if entry[0] == "gurobi time":
                        times.append(float(entry[1]))
                    if entry[0] == "result":
                        result = entry[1]
            #read in the moves made from the decisions csv
            with open(f"{RESULTS_FOLDER}/{turn_folder}/{DECISIONS_CSV}", newline='') as decisionscsv:
                csvreader = csv.reader(decisionscsv, delimiter=",")
                firstmove = False #we are only interested in those listed under "Scenario (0,)"
                for entry in csvreader:
                    #if this line is a scenario labelling, use that to 
                    if "Scenario" in entry[0]:
                        firstmove = True if entry[0] == "Scenario (0,)" else False
                    elif firstmove: #process any other lines if firstmove is currently true
                        #unpack each of the columns
                        piece = Piece[entry[0].split(".")[1]]
                        rotation = Rotation[entry[1].split(".")[1]]
                        flip = entry[2] == "True"
                        row = int(entry[3])
                        col = int(entry[4])
                        #append this to the moves made list
                        moves_made.append((Tile(piece, rotation, flip), (row,col), turn))   
            return result #should be defined by now
        else:
            return -1
       
    """
    play a full game of Railroad Ink with the given player and dice rolls (from the seed)
    """
    def play_game(self, print_pictures=False, print_output=False):
        #start by creating an empty board
        board = Board()
        #initialise the game dice rolls using the seed
        rolls = generate_game_rolls(self._game_seed)
        
        #ensure there is an empty folder
        #if the folder already exists, leave it because we might be able to reuse some things
        if not path.exists(self._folder):
            create_empty_folder(self._folder)
        
        times = [] #track the times of each of the runs
        moves_made = [] #track all the moves made so that they can be put into a csv at the end
        
        #go through every turn
        for turn in range(1,TURNS+1):
            
            #work out where to save the run information to
            turn_folder = "{0}/Turn-{1}".format(self._call_folder, turn)
            
            #check for if this has already been run
            result = self._check_for_existing_calculation(turn_folder, turn, times, moves_made)
            if result  != -1: #if there was actually an existing solve, continue
                continue
            
            self._update_kwargs_dict(turn)
            
            #solve the turn
            s = self._solve_turn(board, moves_made, rolls[turn-1], turn, turn_folder, print_output)
            result = s.get_result()
            #update the list of solve times
            times.append(s.get_gurobi_runtime())
        
        if print_pictures:
            board.fancy_board_print(file="{0}/{1}".format(self._folder, PHOTO_FILENAME))
                
        #now make a CSV containing the scoring information about the run and get the calculated score
        self._make_score_csv(board)
        
        self._make_info_csv(times)
        self._make_moves_csv(moves_made)
            
        #return the final score
        return result
    
    """
    determines the dice rolls which will be used to call the solver
    """
    def _get_dice_rolls(self, roll):
        if "rolls" not in self._kwargs:
            return [[DiceRoll(roll, 1)]]
        else:
            return generate_scenario(roll, self._kwargs["rolls"])
    
    """
    updates the currently stored kwargs with the changes on the given turn
    """
    def _update_kwargs_dict(self, turn):
        turnName = 'TURN {0}'.format(turn)
        #update any dictionary entries that are to be overridden (if there are any at all)
        #if there is no entry, just iterate through an empty dictionary (i.e do nothing)
        for kw in self._config.get(turnName, {}):
            self._kwargs[kw] = self._config[turnName][kw]        
    
    """
    make a csv containing the score information of the game, note that this calculation does not use the MILP result
    but rather uses the board to calculate the score.
    Returns the final score to be confirmed that it matches the returned result
    """
    def _make_score_csv(self, board):
        #do the score calculation using the board function 'score' which determines the score and its composition
        score, joining_exits_points, longest_railway, longest_highway, centre_points, errors = board.score()
        scoreFile = "{0}/{1}".format(self._folder, SCORE_CSV)
        with open(scoreFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Score", score])
            csv_writer.writerow(["Connecting Exits", joining_exits_points])
            csv_writer.writerow(["Longest Railway", longest_railway])
            csv_writer.writerow(["Longest Highway", longest_highway])
            csv_writer.writerow(["Centre Points", centre_points])
            csv_writer.writerow(["Errors", errors])
        return score
    
    """
    make a csv containing information about the run, including the time taken overall and for each step
    """
    def _make_info_csv(self, times):
        infoFile = "{0}/{1}".format(self._folder, INFO_CSV)
        with open(infoFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Total time", round(sum(times),2)])
            for i in range(TURNS):
                csv_writer.writerow(["Turn " + str(i+1) + " time", times[i]])
            
    """
    make a csv containing all the moves made throughout the whole game
    """
    def _make_moves_csv(self, all_moves):
        movesFile = "{0}/{1}".format(self._folder, MOVES_CSV)
        with open(movesFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Piece", "Rotation", "Flip", "Row", "Col", "Turn"])
            for move in all_moves:
                csv_writer.writerow([move[0].get_piece(), move[0].get_rotation(), move[0].get_flip(),
                                     move[1][0], move[1][1], move[2]]) 
    
    """
    create a csv with the scores of all of the different scenarios for the given results
    """
    def _evaluate_csv(self, results):   
        evaluateFile = "{0}/{1}".format(self._folder, EVALUATE_CSV)
        with open(evaluateFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            for i in range(len(self._all_rolls)):
                csv_writer.writerow([i, results[i]])
                
    """
    creates a csv with all the information from the scores of all of the runs
    """
    def _comparison_csv(self, move_results):
        comparisonFile = "{0}/{1}".format(self._folder, COMPARISON_CSV)
        with open(comparisonFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Scenario"] + [f"Roll {i}" for i in range(len(move_results))])
            for i in range(len(self._all_rolls)):
                csv_writer.writerow([i] + [move_results[move][i] for move in range(len(move_results))])      
        
    
if __name__ == "__main__":
    
    p = RailroadInkPlayer("greedy-delayed-specials", 42)
    p.play_game(print_pictures=True, print_output=True)
    