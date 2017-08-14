"""Tool for connecting to the host PC and sending messages. Use to develop and
test new experiments.

"""

from __future__ import print_function

import sys
import time
import csv
import json
from argparse import ArgumentParser
from collections import namedtuple
from contextlib import contextmanager
from threading import Event
import logging
import sqlite3

import pandas as pd

import zmq
from zmq.eventloop.ioloop import ZMQIOLoop
from zmq.eventloop.future import Context
from tornado import gen
from tornado.options import options
from tornado.log import enable_pretty_logging

try:
    from tqdm import tqdm
except ImportError:
    print("You should pip install tqdm")
    tqdm = lambda x: x

from ramcontrol.messages import get_message_type

logger = logging.getLogger("debugger")
ScriptedMessage = namedtuple("Message", "delay, msg")


def parse_csv_file(filename):
    """Read through a CSV file specifying a sequence of messages to send. The
    format is::

        delay time in s,message type,keyword args as JSON string for the message

    The message type should be the capitalized message name as used in the
    :class:`RAMMessage` base class when constructing new messages; e.g., the
    type is `TRIAL` to send a :class:`TrialMessage`.

    :param str filename:
    :returns: a list of tuples specifying the delay and the message object to
        transmit

    """
    with open(filename, "r") as csvfile:
        reader = csv.reader(csvfile.readlines(), delimiter=";")

    messages = []
    t0 = time.time()

    for row in reader:
        if row[0].startswith("#"):
            continue
        else:
            delay, mtype, params = float(row[0]), row[1], row[2]

        if params == "":
            kwargs = dict()
        else:
            kwargs = json.loads(params)
            if mtype == "STATE":
                state = kwargs.pop("name")
                kwargs["state"] = state
            elif mtype == "SESSION":
                try:
                    session = kwargs.pop("session_number")
                    kwargs["session"] = session
                except KeyError:
                    pass
        kwargs["timestamp"] = (t0 + delay)*1000.
        msg = get_message_type(mtype)(**kwargs)
        messages.append(ScriptedMessage(delay, msg))

    return messages


def generate_scripted_session(logfile, outfile=None):
    """Generate a CSV-scripted session from a Ramulator output log.

    Currently, the following message types are ignored:

    * ``HEARTBEAT``
    * ``ALIGNCLOCK``
    * ``SYNC``
    * ``MATH``
    * ``WORD``

    :param str logfile: Log file to read.
    :param str outfile: Output CSV file or None.
    :rtype:

    """
    ignore = ["HEARTBEAT", "SYNC", "MATH", "WORD", "ALIGNCLOCK", "EXPNAME",
              "VERSION", "SUBJECTID", "SESSION"]

    if logfile.endswith('sqlite'):
        with sqlite3.connect(logfile) as conn:
            logs = pd.read_sql_query('SELECT * FROM logs WHERE name = "rampy.zmqsocket"', conn)

        # Parse messages
        messages = [json.loads(msg.split("Incoming message: ")[1])
                    for msg in logs[logs.msg.str.startswith('Incoming message:')].msg]
    else:
        messages = []
        with open(logfile) as f:
            for line in f.readlines():
                entry = line.split("Incoming message: ")
                if len(entry) is not 2:
                    continue
                messages.append(json.loads(entry[-1]))

    # Remove ignored message types
    df = pd.DataFrame(messages)
    df = df[~df.type.isin(ignore)]
    df.reset_index(inplace=True)

    # Convert to time deltas in seconds
    df.time /= 1000.
    df.time = pd.Series([0] + [df.time.iloc[n] - df.time.iloc[n - 1]
                               for n in range(1, len(df.time))])

    # For some reason, we sometimes get negative times... Just make those 10 ms.
    df.time = df.time.apply(lambda x: 0.01 if x <= 1e-3 else x)

    kwargs = df.data
    kwargs = kwargs.apply(lambda x: "" if x is None else json.dumps(x))

    csv = pd.DataFrame({
        "delay": df.time,
        "msgtype": df.type,
        "kwargs": kwargs
    })

    lines = ["#delay;msgtype;kwargs",
             "0;CONNECTED;"]
    lines += [
        "{:f};{:s};{:s}".format(row.delay, row.msgtype, row.kwargs)
        for _, row in csv.iterrows()
    ]
    output = "\n".join(lines)

    if outfile is not None:
        print("Writing to " + outfile + "...")
        with open(outfile, "w") as f:
            f.write(output)

    return output


@contextmanager
def socket():
    """Context manager to give the bound socket."""
    ctx = Context()
    sock = ctx.socket(zmq.PAIR)
    sock.bind("tcp://*:8889")
    yield sock
    sock.close()


def run_message_sequence(filename, heartbeat):
    """Run through a list of scripted messages.

    :param str filename: CSV sequence filename.
    :param bool heartbeat: Send heartbeats every second once connected.

    """
    done = Event()

    with socket() as sock:
        @gen.coroutine
        def send_msg(mtype):
            yield sock.send(get_message_type(mtype)().jsonize())

        @gen.coroutine
        def recv():
            while True:
                incoming = yield sock.recv()
                logger.debug("Received %s" % incoming)

        @gen.coroutine
        def wait_for_connection():
            logger.info("Waiting for connection ")
            incoming = yield sock.recv()
            logger.debug("Received %s", incoming)
            logger.info("Connected!")
            yield send_msg("CONNECTED")

        @gen.coroutine
        def wait_for_start():
            ready = False
            logger.info("Waiting for start message...")
            while not ready:
                incoming = yield sock.recv()
                msg = json.loads(incoming)
                logger.debug("%s", incoming)
                if msg["type"] != "START":
                    continue
                ready = True
                logger.info("Got start")

        @gen.coroutine
        def send_sequence(sequence):
            for entry in sequence:
                logger.info("Delaying for %.3f s...", entry.delay)
                yield gen.sleep(entry.delay)
                jsonized = entry.msg.jsonize()
                logger.info("Sending %s", jsonized)
                sock.send(jsonized)

        @gen.coroutine
        def send_heartbeats():
            if heartbeat:
                logger.info("Sending heartbeats...")
                while not done.is_set():
                    yield send_msg("HEARTBEAT")
                    yield gen.sleep(1)

        @gen.coroutine
        def main():
            sequence = parse_csv_file(filename)
            yield wait_for_connection()
            send_heartbeats()
            # yield wait_for_start()
            recv_future = recv()
            yield send_sequence(sequence)
            yield send_msg("EXIT")
            recv_future.cancel()
            done.set()

        loop = ZMQIOLoop.instance()
        loop.run_sync(main)


if __name__ == "__main__":
    parser = ArgumentParser(description="Connect and send messages to the host PC.")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable extra verbose output")

    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser(
        "generate", help="Generate a CSV file from host PC output logs")
    generate.add_argument("-o", "--outfile", type=str, default="",
                          help="Output file")
    generate.add_argument("-f", "--filename", type=str, required=True,
                          help="Log file to read")

    run = subparsers.add_parser("run", help="Run a scripted session")
    run.add_argument("-f", "--file", type=str, dest="filename",
                     help="File to read for scripting messages to send")
    run.add_argument("-b", "--no-heartbeat", action="store_false",
                     dest="heartbeat", default=True,
                     help="Send heartbeat messages to ensure the host PC stays alive.")

    args = parser.parse_args()

    if args.debug:
        options.logging = "debug"
    enable_pretty_logging()

    if args.command == "generate":
        funcargs = [args.filename]
        write_to_stdout = len(args.outfile) == 0
        if not write_to_stdout:
            funcargs.append(args.outfile)

        out = generate_scripted_session(*funcargs)

        if write_to_stdout:
            sys.stdout.write(out)

    elif args.command == "run":
        if args.filename is not None:
            run_message_sequence(args.filename, args.heartbeat)
        else:
            run.print_help()
