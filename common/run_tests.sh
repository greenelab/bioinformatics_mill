#!/bin/bash

# script for executing Django PyUnit Tests within a Docker container.

# This script should always run as if it were being called from
# the directory it lives in.
script_directory=`perl -e 'use File::Basename;
 use Cwd "abs_path";
 print dirname(abs_path(@ARGV[0]));' -- "$0"`
cd $script_directory

# However in order to give Docker access to all the code we have to
# move up a level
cd ..

docker build -t common_tests -f common/Dockerfile .

if [ `uname` == "Linux" ]; then
    export HOST_IP=$(ip route get 8.8.8.8 | awk '{print $NF; exit}')
elif [ `uname` == 'Darwin' ]; then # MacOS
    export HOST_IP=$(ifconfig en0 | grep inet | awk '{print $2; exit}')
fi

docker run \
       --add-host=database:$HOST_IP \
       --add-host=nomad:$HOST_IP \
       --env-file common/environments/test \
       -i common_tests test --no-input "$@"
