#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=8000
#noSBATCH -o /dev/null
#change noSBATCH to SBATCH to remove slurm outputs
#simply runs the railroadInkGame.py python file with the given params
#this has to be called with sbatch
python pythonfiles/railroadInkGame.py "$@"

