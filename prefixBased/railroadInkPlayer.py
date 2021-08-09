from railroadInkSolver import RailroadInkSolver, RESULTS_FOLDER, create_empty_folder
from board import Board, Tile, Piece, Rotation, DiceRoll, BASIC_PIECES, JUNCTION_PIECES
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
BOARDS_FOLDER = "boards"

#RANDOM MOVE GENERATION FILES

"""
generates the rolls for a single game of Railroad Ink
this would be refactored to be a loop over the below function
but it would change how the rolls are generated so can't be changed
"""
def generate_game_rolls(game_seed):
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
generate a roll for a single turn of Railroad Ink
"""
def generate_game_roll(game_seed):
    random.seed(game_seed)
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
    plays a single turn of Railroad Ink with the given player, board from the given scenario/board file
    and moves generated with given seed
    """
    def play_turn(self, print_pictures=False, print_output=False):
        #start by determining the moves with the given scenario and what turn we are up to
        all_moves, turn = self._get_starting_moves()
        #then load these into a board
        board = Board()
        for move in all_moves:
            board.add_tile(move[0], move[1], move[2])
        #then generate the roll 
        roll = generate_game_roll(self._game_seed)
        #determine how the player is supposed to make decisions at this turn by updating the kwargs
        #at each turn up until now
        for i in range(1, turn + 1):
            self._update_kwargs_dict(turn)
        #determine the dice_rolls to use
        dice_rolls = self._get_dice_rolls(roll)
        

        
        #run the game
        s = RailroadInkSolver(board, turn, dice_rolls, **self._kwargs)
        s.solve(folder=self._call_folder, print_output=print_output)
        
        #unpack the moves that were made and add them to all_moves
        moves = s.get_moves_made()[(0,)]
        for square, tile in moves:
            board.add_tile(tile, square, turn)
            all_moves.append((tile, square, turn))
            
        if print_pictures:
            board.fancy_board_print(file="{0}/{1}".format(self._folder, PHOTO_FILENAME))     
            
        #make a csv for the moves made
        self._make_moves_csv(all_moves)
        #        
       
    """
    play a full game of Railroad Ink with the given player and dice rolls (from the seed)
    """
    def play_game(self, print_pictures=False, print_output=False):
        #start by creating an empty board
        board = Board()
        #initialise the game dice rolls using the seed
        self._rolls = generate_game_rolls(self._game_seed)
        
        #ensure there is an empty folder
        create_empty_folder(self._folder)
        
        times = [] #track the times of each of the runs
        all_moves = [] #track all the moves made so that they can be put into a csv at the end
        
        #go through every turn
        for turn in range(1,TURNS+1):
            
            #work out where to save the run information to
            turn_folder = "{0}/Turn-{1}".format(self._call_folder, turn)
            
            self._update_kwargs_dict(turn)
            dice_rolls = self._get_dice_rolls(self._rolls[turn-1])
            
            s = RailroadInkSolver(board, turn, dice_rolls, **self._kwargs)
            
            s.solve(folder=turn_folder, print_output=print_output)
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
    def _get_dice_rolls(self, roll):
        return [[DiceRoll(roll, 1)]]
    
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
    