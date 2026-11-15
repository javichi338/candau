#!/bin/bash

if [ $0 != 3 ] then
    echo 'USAGE: ./autoConfCandau.sh [backendurl] [token-enroll] [PK-configure]'
    exit 1
fi

backendurl=$1
tokenEnroll=$2
pkConfigure=$3

