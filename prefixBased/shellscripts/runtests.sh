#!/bin/bash

#this file contains example calls for running on the cluster
#note that the file structure was slightly different on the cluster
#with all the Python files being in a folder called 'pythonfiles' and
#these being in the top level directory

#RUN FULL GAMES
#./batchrunner.sh full-game-players/open-ends timeout6hr.txt 1 100
#./batchrunner.sh full-game-players/fake-connections timeout6hr.txt 1 100

#RUN SINGLE TURNS WITH MULTIPLE DIFFERENT SOLUTIONS BEING EVALUATED
#./batcheval.sh turn-6-solvers/one-generic-scenario-timeout turn-6 timeout150.txt 1 100

#RUN SINGLE TURNS WITH A SINGLE SOLUTION
#./batchturn.sh turn-6-solvers/greedy turn-6 timeout12hrrepeated.txt 1 100

#AGGREGATE RESULTS FROM A BATCH OF RUNS
#sbatch --time=0:04 runpython.sh aggregate full-game/full-game-players/perfect-look-ahead
#python3 pythonfiles/railroadInkGame.py aggregate full-game/full-game-players/fake-connections

#COMPARE RESULTS FROM MULTIPLE DIFFERENT BATCHES
#sbatch --time=0:10 runpython.sh compare turn-6 turn-6-solvers/two-generic-scenarios-timeout turn-6-solvers/two-generic-scenarios turn-6-solvers/two-selected-timeout
#sbatch --time=0:10 runpython.sh compare full-game full-game-players/internal-sinks full-game-players/open-ends full-game-players/fake-connections full-game-players/greedy-delayed
#python3 pythonfiles/railroadInkGame.py compare full-game full-game-players/greedy-delayed full-game-players/perfect-look-ahead

