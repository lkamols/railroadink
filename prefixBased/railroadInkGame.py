#author Luke Kamols
#this file is purely used for command line calls to the railroad ink player

import sys
import os
import csv
import numpy as np
import statistics
from board import Board, Piece, Rotation, Tile
from railroadInkSolver import RESULTS_FOLDER
from railroadInkPlayer import RailroadInkPlayer, INFO_CSV, SCORE_CSV, MOVES_CSV, PHOTO_FILENAME


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
        #if the argument is 'play' then play a full game using the next arguments
        player = RailroadInkPlayer(sys.argv[2], int(sys.argv[3]))
        player.play_game(print_pictures=False, print_output=False)
    elif sys.argv[1] == "aggregate":
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
        #if the argument is "genpic" then generate a picture out of the moves csv in the given folder and
        #store the picture in the same folder
        #the argument is the folder position relative to the results directory
        folder = "{0}/{1}".format(RESULTS_FOLDER, sys.argv[2])
        movesfile = "{0}/{1}".format(folder, MOVES_CSV)
        board = board_from_file(movesfile)
        board.fancy_board_print(file="{0}/{1}".format(folder, PHOTO_FILENAME))
    elif sys.argv[1] == "turn":
        pass
    else:
        raise ValueError("Invalid argument supplied, must be one of\n\t'play', 'aggregate', 'genpic', 'turn'")
