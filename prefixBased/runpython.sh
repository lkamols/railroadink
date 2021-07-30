#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=1000
#SBATCH -o /dev/null

#simply runs the railroadInkGame.py python file with the given params
#this has to be called with srun
#this srun, conda activate has to be added to play nicely with Gurobi licensing
conda activate or
python pythonfiles/railroadInkGame.py "$@"

