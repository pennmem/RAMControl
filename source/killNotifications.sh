#!/bin/bash

sudo defaults write /System/Library/LaunchAgents/com.apple.notificationcenterui KeepAlive -bool false

sudo killall NotificationCenter
