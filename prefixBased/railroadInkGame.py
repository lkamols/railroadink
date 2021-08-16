#author Luke Kamols
#this file is purely used for command line calls to the railroad ink player

import sys
import os
import csv
import numpy as np
import statistics
import math
from board import Board, Piece, Rotation, Tile, DiceRoll
from railroadInkSolver import RESULTS_FOLDER
from railroadInkPlayer import RailroadInkPlayer, INFO_CSV, SCORE_CSV, MOVES_CSV, EVALUATE_CSV, PHOTO_FILENAME

COMPARE_CSV = "compare.csv"


"""
taking a list of files, read them as csvs and merge the results into a dictionary of all the contents of the files
also returns a list of the entries to maintain an order
"""
def merge_statistics(files):
    results = {} #dictionary to store all the results
    order = []
    for file in files:
        with open(file, newline='') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=",")
            for row in csvreader:
                stat = row[0]
                val = float(row[1])
                if stat not in results:
                    results[stat] = []
                    order.append(stat)
                results[stat].append(val)
    return results, order

"""
taking the result of the merge_statistics function and a file to create a csv at,
creates a csv with the aggregate information (mean, stddev, min, median, max)
"""
def create_aggregate_csv(datalists, order, file):
    #now write to a csv all the results
    with open(file, mode="w", newline='') as printcsv:
        csvwriter = csv.writer(printcsv, delimiter=",")
        csvwriter.writerow(["", "Mean", "StdDev", "Min", "Median", "Max"])
        for entry in order:
            data = datalists[entry] #get the list of data associated with this entry
            #then enter the data
            csvwriter.writerow([entry, round(np.mean(data),2), round(np.std(data),2), min(data), statistics.median(data), max(data)])    

"""
takes a file and reads in the moves stored in it to create a board with those moves made
returns the created board
"""
def board_from_file(file):
    board = Board() #start a fresh board
    with open(file, newline='') as movescsv:
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
                board.add_tile(Tile(piece, rotation, flip), (row,col), turn)
    return board

if __name__ == "__main__":
    
    #the first argument determines what to do
    if sys.argv[1] == "play":
        #use: play player-name seed
        #if the argument is 'play' then play a full game using the next arguments
        player = RailroadInkPlayer(sys.argv[2], int(sys.argv[3]))
        player.play_game(print_pictures=False, print_output=False)
    elif sys.argv[1] == "aggregate":
        #use: aggregate player-name
        #if the argument is 'aggregate' then go through all of the runs that have been done
        #with the given argument player
        #get the list of subdirectories in the given folder
        player_name = sys.argv[2]
        folder_contents = os.listdir("{0}/{1}".format(RESULTS_FOLDER, player_name))
        
        #we want to aggregate both the info csv and the score csv
        for csvfile in [INFO_CSV, SCORE_CSV]:
            runs = [f"{RESULTS_FOLDER}/{player_name}/{f}/{csvfile}" for f in folder_contents if "Seed" in f]
            datalists, order = merge_statistics(runs)
            create_aggregate_csv(datalists, order, f"{RESULTS_FOLDER}/{player_name}/{csvfile}")
    elif sys.argv[1] == "genpic":
        #use: genpic path-to-folder
        #if the argument is "genpic" then generate a picture out of the moves csv in the given folder and
        #store the picture in the same folder
        #the argument is the folder position relative to the results directory
        folder = "{0}/{1}".format(RESULTS_FOLDER, sys.argv[2])
        movesfile = "{0}/{1}".format(folder, MOVES_CSV)
        board = board_from_file(movesfile)
        board.fancy_board_print(file="{0}/{1}".format(folder, PHOTO_FILENAME))
    elif sys.argv[1] == "turn":
        #use: turn player seed scenario
        #if the argument is "turn" then do a single turn from the state given in boardfile
        #first load in the board
        player = RailroadInkPlayer(sys.argv[2], int(sys.argv[3]), sys.argv[4])
        player.play_turn(print_pictures=False, print_output=True)
    elif sys.argv[1] == "evaluate":
        #use: evaluate player seed scenario
        #does one step, then evaluates that move with the given player for all possible dice
        #rolls on the next move
        player = RailroadInkPlayer(sys.argv[2], int(sys.argv[3]), sys.argv[4])
        player.evaluate_turn(print_pictures=False, print_output=True)
    elif sys.argv[1] == "compare":
        #use: compare scenario {players}
        #compares all players for the given scenario and determines the likelihood of them winning
        #every single seed
        
        #start by getting the path to the directory being compared
        folder = f"{RESULTS_FOLDER}/{sys.argv[2]}"
        if len(sys.argv) > 3:
            players = sys.argv[3:]
        else:
            players = os.listdir(folder)
        #use all of the seeds in the folder of the first player
        seeds = os.listdir(f"{folder}/{players[0]}")
        seeds.sort() #put these in order
        
        #get all of the possible dice rolls for determining probabilities
        dice_rolls = DiceRoll.get_full_distribution()
        
        #we will be writing the results to a csv
        with open(f"{folder}/{COMPARE_CSV}", mode="w", newline='') as printcsv:
            csvwriter = csv.writer(printcsv, delimiter=",")
            csvwriter.writerow(["Seed"] + players)
            #for each of the seeds/games, run through all the players and work out who wins
            for seed in seeds:
                scores = {}
                #read each players scores for this seed and save them
                for player in players:
                    scores[player] = [] 
                    evalfile = f"{folder}/{player}/{seed}/{EVALUATE_CSV}"
                    #determine if the file exists
                    if os.path.isfile(evalfile):
                        with open(evalfile, newline='') as evalcsv:
                            csvreader = csv.reader(evalcsv, delimiter=",")
                            for line in csvreader:
                                scores[player].append(float(line[1])) #the score in that scenario is the second entry
                    else:
                        #if the file doesn't exist, just make -1 values as flags
                        scores[player] = [-1]*len(dice_rolls)
                #now we need to calculate the win probabilities
                
                win_probs = {player : 0 for player in players} #start all at zero
                for game_index in range(len(dice_rolls)):
                    #get the winning score
                    winning_score = max(scores[player][game_index] for player in players)
                    game_prob = dice_rolls[game_index].get_probability()
                    for player in players:
                        if math.isclose(scores[player][game_index], winning_score):
                            win_probs[player] += game_prob
                        elif scores[player][game_index] == -1:
                            win_probs[player] = "MISSING"
                #now print this to the collated csv
                csvwriter.writerow([seed] + [win_probs[player] for player in players])
    else:
        raise ValueError("Invalid argument supplied, must be one of\n\t'play', 'aggregate', 'genpic', 'turn', 'evaluate', 'compare'")
