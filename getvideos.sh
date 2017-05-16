#!/usr/bin/env bash
mkdir -p ./videos
read -p "rhino username: " username
rsync -rzP $username@rhino2.psych.upenn.edu:/data/RAM_videos/* ./videos
