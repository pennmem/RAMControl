set choiceKeys to {"J", "K"}
set dt to 0.7
repeat 20000 times
    tell application "System Events" to keystroke (random number from 1 to 9)
    delay dt
    tell application "System Events" to keystroke Return
    delay dt
    tell application "System Events" to keystroke item (random number from 1 to 2) of choiceKeys
    delay dt
end repeat
