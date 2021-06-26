
from abc import ABC, abstractmethod
from railroadInkSolver import RailroadInkSolver, RESULTS_FOLDER
from board import Board, DiceRoll, BASIC_PIECES, JUNCTION_PIECES
import random
import csv

TURNS = 7
ARENA_FOLDER = "arena"
PHOTO_FILENAME = "solution.png"

SCORE_CSV = "score.csv"
INFO_CSV = "info.csv"
ERROR_FILE = "MISMATCH.txt"

"""
abstract class for a player of the game, has the ability to run a full game
simulation, using a sub class implementation for choosing moves
"""
class Player(ABC):
    
    def __init__(self):
        pass
    
    def play_game(self, actual_dice_rolls, folder=None, printPictures=False, printOutput=False):
        #start by creating an empty board
        board = Board()
        
        times = [] #track the times of each of the runs
        
        #go through every turn
        for turn in range(1,TURNS+1):
            #work out where to save the run information to
            if folder == None:
                turnFolder = None
            else:
                turnFolder = "{0}/{1}".format(folder, turn)
            
            #firstly we generate the move, using the subclasses decision making system
            s = self._move_model(board, turn, actual_dice_rolls[turn-1])
            
            s.solve(folder=turnFolder, printOutput=printOutput)
            #now we need to get out the information from this
            #we only care about the moves made on the first turn, sequence (0,)
            moves = s.get_moves_made()[(0,)]
            #now add all the moves made to the board
            for square, tile in moves:
                board.add_tile(tile, square, turn)
            #update the list of solve times
            times.append(s.get_gurobi_runtime())
        
        if printPictures:
            if folder == None:
                board.fancy_board_print()
            else:
                board.fancy_board_print(file="{0}/{1}/{2}".format(RESULTS_FOLDER, folder, PHOTO_FILENAME))
                
        #now make a CSV containing the scoring information about the run and get the calculated score
        score = self._make_score_csv(board, folder)
        
        self._make_info_csv(folder, times)
            
        #do a double check that the result of the MILP and the board calculation are the same
        #these are not necessarily going to be the same depending on the solver, so raising an error
        #isn't really appropriate, and if there are batch results then any printing won't do much
        #so create a file 
        if score != s.get_result():
            errorPath = "{0}/{1}/{2}".format(RESULTS_FOLDER, folder, ERROR_FILE)
            with open(errorPath, 'w') as errorFile:
                errorFile.write("MILP: {0}\nBoard: {1}".format(s.get_result(), score))
            
        #return the final score
        return s.get_result()
    
    """
    make a csv containing the score information of the game, note that this calculation does not use the MILP result
    but rather uses the board to calculate the score.
    Returns the final score to be confirmed that it matches the returned result
    """
    def _make_score_csv(self, board, folder):
        #do the score calculation using the board function 'score' which determines the score and its composition
        score, joining_exits_points, longest_railway, longest_highway, centre_points, errors = board.score()
        scoreFile = "{0}/{1}/{2}".format(RESULTS_FOLDER, folder, SCORE_CSV)
        with open(scoreFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Score", "Connecting Exits", "Longest Railway", "Longest Highway", "Centre Points", "Errors"])
            csv_writer.writerow([score, joining_exits_points, longest_railway, longest_highway, centre_points, errors])
        return score
    
    """
    make a csv containing information about the run, including the time taken overall and for each step
    """
    def _make_info_csv(self, folder, times):
        infoFile = "{0}/{1}/{2}".format(RESULTS_FOLDER, folder, INFO_CSV)
        with open(infoFile, mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(["Total time", round(sum(times),2)])
            for i in range(TURNS):
                csv_writer.writerow(["Turn " + str(i+1) + " time", times[i]])
            
            
          
    """
    generate the model used for making the move, this will be overridden in a subclass
    to allow for different move makers
    """
    @abstractmethod
    def _move_model(self, board, turn, dice):
        pass
    
    """
    the name to use for each player
    """
    @abstractmethod
    def player_name(self):
        pass
        
 
"""
the simplest player, gets as many points as possible on every turn, delaying all special moves
until the last 3 turns
"""       
class GreedyPlayer(Player):
    
    def __init__(self):
        pass
    
    #overriding abstract method
    def _move_model(self, board, turn, dice):
        #only use the special piece if turn > 4 (i.e on the last 3 turns)
        return RailroadInkSolver(board, turn, [[DiceRoll(dice, 1)]], "expected-score", connecting_exits=False, specials=(turn>4))
        #return RailroadInkSolver(board, turn, [[DiceRoll(dice, 1)]], "expected-score", specials=(turn>4))

    
    #overriding abstract method
    def player_name(self):
        return "Greedy"
    
    
class OpenEndsPlayer(Player):
    
    def __init__(self):
        pass
    
    #overriding abstract method
    def _move_model(self, board, turn, dice):
        #only use the special piece if turn > 4 (i.e on the last 3 turns)
        return RailroadInkSolver(board, turn, [[DiceRoll(dice, 1)]], "expected-score", isolated_pieces="relief", open_ends=True, specials=(turn>4))

    
    #overriding abstract method
    def player_name(self):
        return "Open Ends"
    
    
class OnePieceLookAheadPlayer(Player):
    
    def __init__(self):
        pass
    
    def _move_model(self, board, turn, dice):
        #unless it is the last move, make the move with a look ahead with one extra piece of each
        if turn == 7:
            diceRoll = [[DiceRoll(dice, 1)]]
        else:
            diceRoll = [[DiceRoll(dice, 1)],[DiceRoll({piece: 1},1/9) for piece in BASIC_PIECES + JUNCTION_PIECES]]
        #only use the special piece if turn > 4 (i.e on the last 3 turns)
        return RailroadInkSolver(board, turn, diceRoll, "expected-score", isolated_pieces="relief",specials=(turn>4))
    
    def player_name(self):
        return "One Piece Look Ahead"
    
    
class FakeConnectionsPlayer(Player):
    
    def __init__(self):
        pass
    
    def _move_model(self, board, turn, dice):
        return RailroadInkSolver(board, turn, [[DiceRoll(dice, 1)]], "expected-score", fake_connections=True, specials=(turn>4))
    
    def player_name(self):
        return "Fake connections player"
    
class InternalSinksPlayer(Player):

    def __init__(self):
        pass
    
    def _move_model(self, board, turn, dice):
        return RailroadInkSolver(board, turn, [[DiceRoll(dice, 1)]], "expected-score", internal_sinks=True, longest_paths=False, specials=(turn>4))

    def player_name(self):
        return "Internal Sinks Player"

"""
class for simulating dice rolls and generating games
"""
class DiceRollSimulator:

    def __init__(self, seed=0):
        random.seed(seed)
        
    """
    generates a list of many different games, each of which is a list of dice rolls
    """
    def generate_game_list(self, trials):
        l = []
        for i in range(trials):
            l.append(self.generate_game_rolls())
        return l
    
    """
    generates the rolls for a single game of Railroad Ink
    """
    def generate_game_rolls(self):
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
   
    
class Arena:
    
    def __init__(self, competitors, folder="arena"):
        self._competitors = competitors
        self._folder = folder
        
    def test(self, trials):
        #start by generating the games to get them to play
        d = DiceRollSimulator()
        games = d.generate_game_list(trials)
    
        #initialise the array that tracks wins for each competitor
        wins = [0] * len(self._competitors) 
        
        #then for each of the games, pit the different models against each other
        for gameIndex in range(len(games)):
            game = games[gameIndex]
            #generate the scores for all the competitors
            scores = []
            for competitor in self._competitors:
                scores.append(competitor.play_game(game, folder="{0}/{1}/game {2}".format(
                        ARENA_FOLDER, competitor.player_name(), gameIndex), printOutput=True, printPictures=True))
                
            #then find the winning score
            win_score = max(scores)
            
            #find any players who got that score
            winners = []
            for i in range(len(scores)):
                if scores[i] == win_score:
                    #we have a winner!
                    winners.append(i)
            
            #now add to the wins of all the winners, less points the more winners there were
            for winner in winners:
                wins[winner] += 1 / len(winners)
        return wins
    
    
if __name__ == "__main__":
    
    d = DiceRollSimulator(42)
    rolls = d.generate_game_rolls()
    
#    i = InternalSinksPlayer()
#    i.play_game(rolls, folder="internal-sinks-player", printPictures=True, printOutput=True)
    
#    la = OnePieceLookAheadPlayer()
#    la.play_game(rolls, folder="one-piece-look-ahead", printPictures=True, printOutput=True)
    
#    f = FakeConnectionsPlayer()
#    f.play_game(rolls, folder="fake-connections-reduced-plays", printPictures=True, printOutput=True)
#    
#    o = OpenEndsPlayer()
#    o.play_game(rolls, folder="test", printPictures=True, printOutput=True)
    
    g = GreedyPlayer()
    g.play_game(rolls, folder="greedy-delayed-no-connecting-exits", printPictures=True, printOutput=True)
 
#    competitors = [GreedyPlayer(), GreedyPlayerWithDelayedSpecials()]
#    arena = Arena(competitors)
#    print(arena.test(2))
    