# Railroad Ink
This is the codebase associated with my 2021 honours thesis 'Optimising Railroad Ink'.
This thesis aimed to develop a program for playing Railroad Ink using operations research techniques.
This repository contains the final program created as well as many different checkpoints and the raw data used to generate the values shown in the thesis.

## Summary
- board.py: contains the underlying Railroad Ink board implementation and algorithms for working out the score of a given board without solving an MILP.
- railroadInkSolver.py: contains the entire framework for constructing and solving MILPs for Railroad Ink problems, uses board.py.
- railroadInkPlayer.py: contains framework for generating games to play and running full games or single turns given configuration files, uses railroadInkSolver.py.
- railroadInkGame.py: contains command line arguments for running games and aggregating data from different runs.
- boards: this folder contains all the board states used for testing. For example, tests run for turn 6 needed to have turns 1 to 5 played already.
- data-generation: this folder contains some excel sheets demonstrating how some of the data aggregation in the submitted thesis were conducted.
- players: this folder contains configuration files which define different approaches to playing Railroad Ink, the file players/full-game-players/perfect-look-ahead.txt contains the best player found.
- Railroad-Pictures: this folder contains images of the board and each of the pieces, this is used to create an image to show a given board state.
- results: this folder contains the raw data associated with the results submitted as part of the thesis.
- shellscripts: this folder contains some shell scripts which were used when running tests on the university cluster. Note that the file structure was different on the cluster, so these are examples and would need to be modified to work locally.
- timeoutfiles: this folder contains files for defining the timeouts associated with individual runs on the university cluster.

## Example Results
Some example results:



## Requirements
This code utilises the Gurobi mathematics solver and so a valid Gurobi license is required to run any MILPs.
For image manipulation the 'Pillow' package is used, install with 'python3 -m pip install --upgrade Pillow'
