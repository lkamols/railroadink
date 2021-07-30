#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=1000
#SBATCH --time=0-0:05
#efefSBATCH -o /dev/null

srun ./runpython.sh play $1 "${SLURM_ARRAY_TASK_ID}"
