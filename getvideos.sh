#!/usr/bin/env bash

for experiment in `ls experiments`; do
    echo "Extracting $experiment videos..."
    cd experiments/$experiment
    tar -xf videos.tar.xz
    cd -
done

echo "done!"
