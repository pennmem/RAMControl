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

import zmq
from zmq.eventloop.ioloop import ZMQIOLoop
from zmq.eventloop.future import Context
from tornado import gen

sys.path.insert(0, "source/pylib")
from messages import get_message_type

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
        reader = csv.reader(csvfile.readlines())

    messages = []
    t0 = time.time()

    for row in reader:
        if row[0].startswith("#"):
            continue
        else:
            delay, mtype, params = float(row[0]), row[1], row[2]

        try:
            kwargs = json.loads(params)
        except:  # no kwargs needed
            kwargs = dict()
        kwargs["timestamp"] = (t0 + delay)*1000.
        msg = get_message_type(mtype)(**kwargs)
        messages.append(ScriptedMessage(delay, msg))

    return messages


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
                print("Received %s" % incoming)

        @gen.coroutine
        def wait_for_connection():
            print("Waiting for connection ")
            incoming = yield sock.recv()
            print("Received %s" % incoming)
            print("Connected!")
            yield send_msg("CONNECTED")

        @gen.coroutine
        def send_sequence(sequence):
            for entry in sequence:
                print("Delaying for %f s..." % entry.delay)
                print(entry.delay)
                yield gen.sleep(entry.delay)
                jsonized = entry.msg.jsonize()
                print("Sending %s" % jsonized)
                sock.send(jsonized, zmq.NOBLOCK)

        @gen.coroutine
        def send_heartbeats():
            while not done.is_set():
                yield sock.send()
                yield gen.sleep(1)

        @gen.coroutine
        def main():
            sequence = parse_csv_file(filename)
            yield wait_for_connection()
            recv_future = recv()
            yield send_sequence(sequence)
            yield send_msg("EXIT")
            recv_future.cancel()
            done.set()

        loop = ZMQIOLoop.instance()
        loop.run_sync(main)


if __name__ == "__main__":
    parser = ArgumentParser(description="Connect and send messages to the host PC.")

    parser.add_argument("-f", "--file", type=str, dest="filename",
                        help="File to read for scripting messages to send")
    parser.add_argument("-b", "--heartbeat", action="store_true", default=True,
                        help="Send heartbeat messages to ensure the host PC stays alive.")

    # TODO: other run modes... should use mutually exclusive groups
    # parser.add_argument("-m", "--message", type=str,
    #                     help="Send a single message of this type")

    args = parser.parse_args()

    if args.filename is not None:
        run_message_sequence(args.filename, args.heartbeat)
    else:
        parser.print_help()
