#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=1000
#SBATCH --time=0-0:05
#eSBATCH -o /dev/null

#srun ./runpython.sh "$@"
conda activate or
python pythonfiles/railroadInkGame.py play $1 $2
#./runpython.sh "$@"
