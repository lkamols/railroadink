#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=1000
#SBATCH --time=0-0:05

srun ./runpython.sh
