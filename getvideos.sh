#!/usr/bin/env bash
read -p "rhino username: " username
scp -Cr $username@rhino2.psych.upenn.edu:/home/depalati/videos .
