from railroadInkSolver import RailroadInkSolver, RESULTS_FOLDER, create_empty_folder
from board import Board, Tile, Piece, Rotation, DiceRoll, BASIC_PIECES, JUNCTION_PIECES
import random
import csv
import json
import math
import numpy as np

TURNS = 7
PHOTO_FILENAME = "solution.png"

SCORE_CSV = "score.csv"
INFO_CSV = "info.csv"
MOVES_CSV = "moves.csv"
EVALUATE_CSV = "evaluation.csv"
ERROR_FILE = "MISMATCH.txt"

BASE_CONFIG_NAME = "INITIAL"

PLAYER_FOLDER = "players"
BOARDS_FOLDER = "boards"

#RANDOM MOVE GENERATION FILES

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
                    include_specials = roll[2]
                else:
                    include_specials = True
                this_turn.append(DiceRoll(pieces, probability, include_specials))
                
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
    using the given scenario and game-seed, find the corresponding board file and load in the moves from it
    these are the starting moves
    returns the moves made, and the turn of the current move
    """
    def _get_starting_moves(self):
        moves = []
        latest_turn = 0 #the latest turn in this scenario
        with open(f"{BOARDS_FOLDER}/{self._scenario}/board{self._game_seed}.csv", newline='') as movescsv:
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
                    latest_turn = max(latest_turn, turn) #update the latest turn
        return moves, latest_turn + 1 #the last turn + 1 is the current turn
    
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
            #now using the new board, evaluate it by running all 162 scenarios
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
        
        #run the game
        s = RailroadInkSolver(board, turn, dice_rolls, **kwargs)
        s.solve(folder=folder, print_output=print_output)
        
        #now check for if multiple solutions were generated and if so evaluate them
        if self._kwargs.get("solution_count", 1) > 1:
            moves = self._compare_moves(board, s, turn, print_output)
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
    given a completed turn, determine the scores for each of the 162 possible dice rolls for the next turn
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
            if "rolls" in kwargs:
                kwargs.pop("rolls")
                
            s = RailroadInkSolver(board, turn, dice_rolls, **kwargs)
            s.solve(folder=None, print_output=print_output)
            results.append(round(s.get_result(),2))
        return results

    """
    create a csv with the scores of all of the different scenarios for the given results
    """
    def _evaluate_csv(self, results):   
        evaluateFile = "{0}/{1}".format(self._folder, EVALUATE_CSV)
        with open(evaluateFile, mode="w", newline="") as csv_file:
            for i in range(len(self._all_rolls)):
                csv_writer = csv.writer(csv_file, delimiter=",")
                csv_writer.writerow([i, results[i]])
        
    """
    take a turn, then evaluate it with the 162 different possible dice rolls, using the next
    turn of the given player
    """
    def evaluate_turn(self, print_pictures=False, print_output=False):
        self.play_turn(print_pictures, print_output) #first play the turn
        if self._kwargs.get("solution_count", 1) > 1:
            return #evaluation was already done
        results = self._evaluate_scenario(self._board, self._turn, print_output)
        self._evaluate_csv(results)
        
       
    """
    play a full game of Railroad Ink with the given player and dice rolls (from the seed)
    """
    def play_game(self, print_pictures=False, print_output=False):
        #start by creating an empty board
        board = Board()
        #initialise the game dice rolls using the seed
        rolls = generate_game_rolls(self._game_seed)
        
        #ensure there is an empty folder
        create_empty_folder(self._folder)
        
        times = [] #track the times of each of the runs
        moves_made = [] #track all the moves made so that they can be put into a csv at the end
        
        #go through every turn
        for turn in range(1,TURNS+1):
            
            #work out where to save the run information to
            turn_folder = "{0}/Turn-{1}".format(self._call_folder, turn)
            
            self._update_kwargs_dict(turn)
            
            #solve the turn
            s = self._solve_turn(board, moves_made, rolls[turn-1], turn, turn_folder, print_output)
            
            #update the list of solve times
            times.append(s.get_gurobi_runtime())
        
        if print_pictures:
            board.fancy_board_print(file="{0}/{1}".format(self._folder, PHOTO_FILENAME))
                
        #now make a CSV containing the scoring information about the run and get the calculated score
        self._make_score_csv(board)
        
        self._make_info_csv(times)
        self._make_moves_csv(moves_made)
            
        #return the final score
        return s.get_result()
    
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
    
if __name__ == "__main__":
    
    p = RailroadInkPlayer("greedy-delayed-specials", 42)
    p.play_game(print_pictures=True, print_output=True)
    