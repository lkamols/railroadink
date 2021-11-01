#!/bin/bash

for ((i=68; i <=100; i++))
do
	printf -v filefrom 'internal-sinks/Seed-%d/moves.csv' $i
	printf -v fileto '/home/uqlkamol/railroad-ink/boards/turn-7/board%d.txt' $i

	sed '/7\r$/d' $filefrom > $fileto
done
