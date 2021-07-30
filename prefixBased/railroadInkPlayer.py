from railroadInkSolver import RailroadInkSolver, RESULTS_FOLDER, create_empty_folder
from board import Board, DiceRoll, BASIC_PIECES, JUNCTION_PIECES
import random
import csv
import json

TURNS = 7
PHOTO_FILENAME = "solution.png"

SCORE_CSV = "score.csv"
INFO_CSV = "info.csv"
MOVES_CSV = "moves.csv"
ERROR_FILE = "MISMATCH.txt"

BASE_CONFIG_NAME = "INITIAL"

PLAYER_FOLDER = "players"

"""
class for a player of the game, has the ability to run a full game
simulation, given some configuration file
"""
class RailroadInkPlayer:
    
    """
    Constructor.
    Creates the given player from the player file by that name which defines how the player will play
    Creates a game with the given game_seed
    """
    def __init__(self, player, game_seed):
        #work out the folder that will be saved to 
        #(the call to RailroadInkSolver prepends the root folder, so have one version without the root)
        self._call_folder = "{0}/Seed-{1}".format(player, game_seed)
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
            
        #initialise the game dice rolls using the seed
        self._rolls = self.generate_game_rolls(game_seed)
       
    """
    play a full game of Railroad Ink with the given player and dice rolls (from the seed)
    """
    def play_game(self, print_pictures=False, print_output=False):
        #start by creating an empty board
        board = Board()
        
        #ensure there is an empty folder
        create_empty_folder(self._folder)
        
        times = [] #track the times of each of the runs
        all_moves = [] #track all the moves made so that they can be put into a csv at the end
        
        #go through every turn
        for turn in range(1,TURNS+1):
            #work out where to save the run information to
            turnFolder = "{0}/Turn-{1}".format(self._call_folder, turn)
            
            self._update_kwargs_dict(turn)
            dice_rolls = self._get_dice_rolls(turn)
            
            s = RailroadInkSolver(board, turn, dice_rolls, **self._kwargs)
            
            s.solve(folder=turnFolder, print_output=print_output)
            #now we need to get out the information from this
            #we only care about the moves made on the first turn, sequence (0,)
            moves = s.get_moves_made()[(0,)]
            #now add all the moves made to the board
            for square, tile in moves:
                board.add_tile(tile, square, turn)
                all_moves += [(tile, square, turn)]
            #update the list of solve times
            times.append(s.get_gurobi_runtime())
        
        if print_pictures:
            board.fancy_board_print(file="{0}/{1}".format(self._folder, PHOTO_FILENAME))
                
        #now make a CSV containing the scoring information about the run and get the calculated score
        score = self._make_score_csv(board)
        
        self._make_info_csv(times)
        self._make_moves_csv(all_moves)
            
        #do a double check that the result of the MILP and the board calculation are the same
        #these are not necessarily going to be the same depending on the solver, so raising an error
        #isn't really appropriate, and if there are batch results then any printing won't do much
        #so create a file 
        if abs(score - s.get_result()) > 0.1:
            errorPath = "{0}/{1}".format(self._folder, ERROR_FILE)
            with open(errorPath, 'w') as errorFile:
                errorFile.write("MILP: {0}\nBoard: {1}".format(s.get_result(), score))
            
        #return the final score
        return s.get_result()
    
    """
    determines the dice rolls which will be used to call the solver
    TO DO expand this to work with future moves as well, not just the current move
    """
    def _get_dice_rolls(self, turn):
        this_turn = self._rolls[turn-1]
        return [[DiceRoll(this_turn, 1)]]
    
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
    generates the rolls for a single game of Railroad Ink
    """
    def generate_game_rolls(self, game_seed):
        random.seed(game_seed)
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
    
#class OnePieceLookAheadPlayer(Player):
#    
#    def __init__(self):
#        pass
#    
#    def _move_model(self, board, turn, dice):
#        #unless it is the last move, make the move with a look ahead with one extra piece of each
#        if turn == 7:
#            diceRoll = [[DiceRoll(dice, 1)]]
#        else:
#            diceRoll = [[DiceRoll(dice, 1)],[DiceRoll({piece: 1},1/9) for piece in BASIC_PIECES + JUNCTION_PIECES]]
#        #only use the special piece if turn > 4 (i.e on the last 3 turns)
#        return RailroadInkSolver(board, turn, diceRoll, "expected-score", isolated_pieces="relief",specials=(turn>4))
#    
#    def player_name(self):
#        return "One Piece Look Ahead"
        
    
if __name__ == "__main__":
    
    p = RailroadInkPlayer("greedy-delayed-specials", 42)
    p.play_game(print_pictures=True, print_output=True)
    