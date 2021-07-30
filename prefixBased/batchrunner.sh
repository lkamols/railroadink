#!/bin/bash

#arguments for this are
#1 - player name
#2 - timeout file
#3 - lower seed index
#4 - upper seed index

#load in the values from the timeout file into an array called 'timeouts'
readarray -t timeouts < "$2"

i=0
while [ $i -lt ${#timeouts[@]} ] 
do
	#see if I currently have any processes running
	activecount=$(squeue -u uqlkamol | wc -l)
	#check if there is room to queue again
	if [ $activecount -eq 1 ] ; then
		echo active1
		added=0
		#work out how long to set the trials to go for
		t=${timeouts[$i]}
		printf -v tt '%d-%02d:%02d' $(( t / 1440 )) $(( (t % 1440) / 60 )) $(( t % 60 ))
		#check through all of the expected results to see if they completed
		for (( seed=$3; seed<=$4; seed++ ))
		do
			#get the right file
			printf -v file '/data/uqlkamol/railroad-ink-results/%s/Seed-%d/info.csv' $1 $seed
			#if that file doesn't exist, this test hasn't been run, queue it
			if [ ! -f $file ] ; then
				echo added run with seed $seed and time $tt
				sbatch --time=${tt} ~/railroad-ink/runpython.sh play $1 $seed
				((added++))
			fi
		done
		echo added $added new jobs
		if [ $added -eq 0 ] ; then
			break
		fi
		i=$(($i + 1))
	fi
	#sleep a while before checking again
	sleep 2m
	echo alive $i $activecount
done
