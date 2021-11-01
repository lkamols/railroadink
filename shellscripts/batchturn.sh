#!/bin/bash

#arguments for this are
#1 - player name
#2 - scenario folder
#2 - timeout file
#3 - lower seed index
#4 - upper seed index

#load in the values from the timeout file into an array called 'timeouts'
printf -v timeoutfile 'timeoutfiles/%s' $3
readarray -t timeouts < $timeoutfile

i=0
while [ $i -lt ${#timeouts[@]} ] 
do
	#see if I currently have any processes running
	activecount=$(squeue -u uqlkamol | wc -l)
	#print the current count of processes
	echo alive $i $((activecount - 1))
	#check if there is room to queue again
	if [ $activecount -eq 1 ] ; then
		added=0
		#work out how long to set the trials to go for
		t=${timeouts[$i]}
		printf -v tt '%d-%02d:%02d' $(( t / 1440 )) $(( (t % 1440) / 60 )) $(( t % 60 ))
		#check through all of the expected results to see if they completed
		for (( seed=$4; seed<=$5; seed++ ))
		do
			#get the right file
			printf -v file '/data/uqlkamol/railroad-ink-results/%s/%s/Seed-%d/info.csv' $2 $1 $seed
			#if that file doesn't exist, this test hasn't been run, queue it
			if [ ! -f $file ] ; then
				echo added run with seed $seed and time $tt
				sbatch --time=${tt} ~/railroad-ink/runpython.sh turn $1 $seed $2
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
done
