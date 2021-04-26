
from abc import ABC, abstractmethod
from railroadInkSolver import RailroadInkSolver
from board import Board, DiceRoll, BASIC_PIECES, JUNCTION_PIECES
import random

TURNS = 7

class Player(ABC):
    
    def __init__(self):
        pass
    
    def play_game(self, actual_dice_rolls, printPictures=False):
        #start by creating an empty board
        board = Board()
        #go through every turn
        for turn in range(TURNS):
            #firstly we generate the move
            s = self._move_model(board, turn, actual_dice_rolls[turn])
            s.solve(folder=None, printOutput=True)
            #now we need to get out the information from this
            #we only care about the moves made on the first turn, sequence (0,)
            moves = s.get_moves_made()[(0,)]
            #now add all the moves made to the board
            for square, tile in moves:
                board.add_tile(tile, square, turn)
                
            print(turn, moves)
        
        if printPictures:
            board.fancy_board_print()
            
    @abstractmethod
    def _move_model(self, board, turn, dice):
        pass
        
        
class GreedyPlayer(Player):
    
    def __init__(self):
        pass
    
    #overriding abstract method
    def _move_model(self, board, turn, dice):
        return RailroadInkSolver(board, turn, [[DiceRoll(dice, 1)]], "expected-score")
    
    
    
class DiceRollSimulator:

    def __init__(self, seed):
        random.seed(seed)
        
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
    
    
if __name__ == "__main__":
    
    d = DiceRollSimulator(42)
    rolls = d.generate_game_rolls()
    
    g = GreedyPlayer()
    g.play_game(rolls, printPictures=True)
    