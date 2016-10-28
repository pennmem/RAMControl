#!/usr/bin/env bash
RAM_DIR="$HOME/RAM"
EXP_ROOT_DIR="$HOME/experiments"
EXP_DIRS=("RAM_FR")  # "RAM_catFR" "RAM_PAL")

mkdir -p $RAM_DIR/logs

if [[ "$?" != "0" ]]; then
    echo "NO INTERNET. TRY AGAIN LATER"
    read
    exit
fi

for EXP_DIR in "${EXP_DIRS[@]}"; do
    echo "$EXP_DIR"
    if [ ! -d "$EXP_ROOT_DIR/$EXP_DIR" ]; then
        svn co "$SVNROOT/RAM/$EXP_DIR" "$EXP_ROOT_DIR/$EXP_DIR"
    else
        if [[ $IS_DEV == 1 ]]; then
            svn revert --depth infinity "$EXP_ROOT_DIR/$EXP_DIR/branches/dev"
            svn up "$EXP_ROOT_DIR/$EXP_DIR/branches/dev" 2> ./.checkSVN
        elif [ ! -d "$EXP_ROOT_DIR/$EXP_DIR/branches/" ]; then
            svn revert --depth infinity "$EXP_ROOT_DIR/$EXP_DIR"
            svn up "$EXP_ROOT_DIR/$EXP_DIR"  2> ./.checkSVN
        else
            svn revert --depth infinity "$EXP_ROOT_DIR/$EXP_DIR/branches/sys2"
            svn up "$EXP_ROOT_DIR/$EXP_DIR/branches/sys2" 2> ./.checkSVN
        fi
    fi

    if [[ $IS_DEV == 1 ]]; then
        RETURN_VAL=$(svn diff "$EXP_ROOT_DIR/$EXP_DIR/branches/dev" 2> ./.checkSVN)
    elif [ ! -d "$EXP_ROOT_DIR/$EXP_DIR/trunk" ]; then
        RETURN_VAL=$(svn diff "$EXP_ROOT_DIR/$EXP_DIR" 2> ./.checkSVN)
    else
        RETURN_VAL=$(svn diff "$EXP_ROOT_DIR/$EXP_DIR/trunk" 2> ./.checkSVN)
    fi

    RETURN_VAL="$RETURN_VAL$(<./.checkSVN)"

    if [[ "$RETURN_VAL" != "" ]]; then

        echo "PROBLEM UPDATING $EXP_DIR."
        echo "Checking internet connection..."
        checkInternet
        if [[ "$?" != "0" ]]; then
            echo "NO INTERNET. TRY AGAIN LATER"
            read
            exit
        fi
        echo "internet connection good."
        echo "**************************" >> /$RAM_DIR/logs/badSVN.log
        date >> $RAM_DIR/logs/badSVN.log
        echo "$RETURN_VAL" >> $RAM_DIR/logs/badSVN.log
        echo "**************************" >> $RAM_DIR/logs/badSVN.log

        echo "CONTACT iped@sas.upenn.edu AND drizzuto@sas.upenn.edu IMMEDIATELY"
        echo "WITH FILE /Users/exp/RAM/logs/badSVN.log ATTACHED"
        echo "PRESS ENTER TO CONTINUE"
        read
    fi
done
