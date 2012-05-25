#!/bin/bash

# Deactivate hyperthreading

processors=`ls -1 /sys/devices/system/cpu | grep -e "cpu[0-9]\{1,\}" | wc -l`

function warn {
    # Echo the provided command in color text.
    yellow='\e[0;33m' # Yellow
    reset='\e[0m'
    echo="echo -e"
    $echo "${yellow}$1${reset}"
}

function set_cores {
    #Cannot enable/disable cpu0
    for ((i=2; i < $1; i+=2))
    do
        warn "Enabling cpu ${i}"
        sudo sh -c "echo 1 > /sys/devices/system/cpu/cpu${i}/online"
    done
    for ((i=1; i < $processors; i+=2))
    do
        warn "Disabling cpu ${i}"
        sudo sh -c "echo 0 > /sys/devices/system/cpu/cpu${i}/online"
    done
}

echo "Disabling hyperthreading: enabling even processors only"
set_cores $processors
