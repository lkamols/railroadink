#author Luke Kamols
#this file is purely used for command line calls to the railroad ink player

import sys
from railroadInkPlayer import RailroadInkPlayer

if __name__ == "__main__":
    
    #the first argument determines what to do
    if sys.argv[1] == "play":
        #if the argument is 'play' then play a full game using the next arguments
        player = RailroadInkPlayer(sys.argv[2], int(sys.argv[3]))
        player.play_game(print_pictures=False, print_output=False)
    else:
        raise ValueError("Invalid argument supplied, must be one of\n\t'play'")
