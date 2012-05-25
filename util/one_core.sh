#!/bin/sh
./mod-cores.sh 1
for i in 2 4 8 16 32 64;
do
  sudo ./CPUIsolationSweep.py -u '0.3,0.35,0.4,0.45,0.5,0.55,0.6,0.65,0.7,0.75,0.8,0.85,0.9,0.95,1.0' -c $i -r 1 -e one_$i --cores 1 -o -m rhone
  sudo mn -c
done
#./plot_cpu_isolation_sweep.py results/rhone/one_*/cpuiso.out  --maxy 0.01 -d ./
#./plot_cpu_isolation_sweep.py results/rhone/one_*/cpuiso.out  --metric cv -p one -d ./

