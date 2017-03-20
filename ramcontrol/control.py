"""Interfaces to the Control PC"""

from __future__ import print_function

import os
from threading import Event
import sys
import logging
from contextlib import contextmanager
import itertools
from multiprocessing import Pipe

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

import zmq
from logserver import create_logger

from pyepl import timing
from pyepl.locals import *
from pyepl.locals import Text
from pyepl.hardware import addPollCallback, removePollCallback

from . import ipc
from .zmqsocket import SocketServer
from .exc import RamException, VoiceServerError
from .messages import *
from .voiceserver import VoiceServer


def default_attempt_callback():
    flashStimulus(Text("Searching for Control PC"), 800)


def default_connecting_callback():
    try:
        flashStimulus(Text("Connecting to Control PC"), 800)
    except AttributeError:
        print("Connecting to control PC")


def default_success_callback():
    flashStimulus(Text("Connection established"), 800)


def default_failure_callback():
    flashStimulus(Text("Connection failed"), 800)


class RAMControl(object):
    """Main controller for running RAM task laptop tasks.

    :param str address: ZMQ address string to bind socket.
    :param int connection_timeout: Network timeout limit in seconds.
    :param int log_level: Log level to use.

    TODO: Make experiment a member of this.
    TODO: Rename to something like ExperimentRunner.

    """
    DEFAULT_HEARTBEAT_INTERVAL = 1000  # ms
    MAX_QUEUE_SIZE = 32
    _instance = None

    def __init__(self, address="tcp://192.168.137.200:8889",
                 connection_timeout=10, log_level=logging.INFO):
        if self._instance is not None:
            raise Exception("Multiple RAM instances requested!")

        self.connection_timeout = connection_timeout

        self._synced = Event()
        self._started = False  # received START from control PC
        self._configured = False
        self._connected = False
        self._connection_failed = False
        self._last_heartbeat_received = -1.  # last time heartbeat was received

        # Experiment-specific data to be filled in later
        self.experiment = ''
        self.version = ''
        self.session_num = -1
        self.subject = ''

        # Configure basic message handlers
        self.handlers = {
            "ID": self.id_handler,
            "SYNC": self.sync_handler,
            "SYNCED": self.synced_handler,
            "START": self.start_handler,
            "EXIT": self.exit_handler,
            "HEARTBEAT": self.heartbeat_handler,
            "CONNECTED": self.connected_handler
        }

        # Enable logging
        self.logger = create_logger("controller", level=log_level)
        self.event_log = create_logger("events")

        try:
            ram_env = json.loads(os.environ["RAM_CONFIG"])

            # Change address if we aren't connecting to the host PC (otherwise
            # there can be ZMQ errors if the network cable is unplugged).
            if ram_env["no_host"]:
                address = "tcp://*:8889"
        except KeyError:
            self.logger.error(
                "No RAM_CONFIG environment variable defined. Proceed with caution."
                " voiceserver assumed to *not* be required!")
            ram_env = {"voiceserver": False}

        self.ctx = zmq.Context()

        self.socket = SocketServer(ctx=self.ctx)
        self.socket.register_handler(self.dispatch)
        self.socket.bind(address)

        if ram_env["voiceserver"]:
            self.voice_pipe, self._voice_child_pipe = Pipe()
            self.voice_server = VoiceServer(self._voice_child_pipe)
            self.voice_socket = self.voice_server.make_listener_socket(self.ctx)
            self.voice_server.start()
        else:
            self.voice_pipe, self._voice_child_pipe = None, None
            self.voice_server = None
            self.voice_socket = None

        self.zpoller = zmq.Poller()
        self.zpoller.register(self.voice_socket, zmq.POLLIN)

    @classmethod
    def instance(cls, *args, **kwargs):  # FIXME: no real reason to do this...
        """Return the singleton :class:`RAMControl` instance."""
        if cls._instance is None:
            cls._instance = RAMControl(*args, **kwargs)
        return cls._instance

    @property
    def synced(self):
        return self._synced.is_set()

    @property
    def network_connected(self):
        return self._connected

    @staticmethod
    def get_system_time_in_micros():
        """Convenience method to return the system time."""
        return time.time() * 1000000.0

    @staticmethod
    def get_system_time_in_millis():
        """Convenience method to return the system time."""
        return int(round(time.time() * 1000.0))

    @staticmethod
    def build_message(msg_type, *args, **kwargs):
        """Build and return a RAMMessage to be sent to control PC."""
        timestamp = kwargs.get("timestamp", None)
        return get_message_type(msg_type)(*args, timestamp=timestamp, **kwargs)

    def shutdown(self):
        """Cleanly disconnect and close sockets and servers."""
        self.logger.info("Shutting down.")
        self.send(ExitMessage())
        if self.voice_server is not None:
            self.voice_server.quit()
            self.voice_socket.close()
            self.voice_server.join(timeout=1)
        self.socket.join()

    def check_connection(self):
        """Checks that we're still connected."""
        if self._last_heartbeat_received > 0:
            t = time.time() - self._last_heartbeat_received
            if t >= self.connection_timeout and self._connected:
                self._connected = False
                self.logger.info("Quitting due to disconnect")
                self.shutdown()
                sys.exit(0)
            else:
                self._connected = True

    @contextmanager
    def voice_detector(self):
        """Context manager to toggle voice activity detection. This will do
        nothing if there is no voice server.

        """
        if self.voice_server is not None:
            # Start it
            self.voice_pipe.send(ipc.message("START"))

            # Wait for acknowledgment
            if not self.voice_pipe.poll(0.1):
                raise VoiceServerError("Didn't get STARTED response")
            response = self.voice_pipe.recv()
            assert response["type"] == "STARTED"

            yield

            # Signal a stop
            self.voice_pipe.send(ipc.message("STOP"))

            # Await acknowledgment
            for _ in range(6):
                if self.voice_pipe.poll(0.1):
                    response = self.voice_pipe.recv()
                    if response["type"] == "STOPPED":
                        break
            else:  # ran out of tries
                raise VoiceServerError("Didn't get STOPPED response")
        else:
            yield

    def check_voice_server(self):
        """Check for messages from the voice server."""
        if self.voice_socket in dict(self.zpoller.poll(1)):  # blocks for 1 ms
            try:
                msg = self.voice_socket.recv_json()
                assert msg["type"] == "VOCALIZATION"
                start = msg["data"]["speaking"]
                log_msg = {
                    "event": "VOCALIZATION_START" if start else "VOCALIZATION_END",
                    "timestamp": msg["data"]["timestamp"]
                }
                self.event_log.info(json.dumps(log_msg))
                self.socket.enqueue_message(
                    self.build_message("STATE", "VOCALIZATION", start))
            except AssertionError:
                self.logger.error("Received a malformed message from the voice server")
            except:
                self.logger.error(
                    "Unknown exception when reading from the voice server",
                    exc_info=True)

        if self.voice_pipe.poll():
            msg = self.voice_pipe.recv()
            if msg["type"] == "CRITICAL":
                try:
                    raise VoiceServerError(msg["data"]["traceback"])
                except:
                    self.logger.critical("VoiceServer failed", exc_info=True)
                    raise
            elif msg["type"] == "TIMESTAMP":
                create_logger("voicetimes").info(json.dumps({
                    "voice_time": msg["data"]["timestamp"],
                    "main_time": time.time() * 1000,
                    "pyepl_time": timing.now()
                }))

    def register_handler(self, name, func):
        """Register a message handler.

        :param str name: Message type to handle.
        :param callable func: Function to call.

        """
        self.handlers[name] = func

    def configure(self, experiment, version, session_num, subject):
        """Set various experiment options so they can be transmitted to the host
        PC and add poll callbacks.

        TODO: move this functionality into ``__init__``.

        :param str experiment:
        :param version:
        :param session_num:
        :param str subject:

        """
        self.experiment = experiment
        self.version = version
        self.session_num = session_num
        self.subject = subject
        self._configured = True

        addPollCallback(self.socket.update)
        addPollCallback(self.check_connection)
        if self.voice_server is not None:
            addPollCallback(self.check_voice_server)

    def send(self, message):
        """Send a message to the host PC."""
        if not isinstance(message, RAMMessage):
            self.logger.error("Cannot send non-RamMessage: %r", message)
        else:
            self.socket.enqueue_message(message)

    def send_experiment_info(self, name, version, subject, session):
        """Sends information about the experiment.

        .. note::

            This is a separate method for now simply because older versions
            required multiple message types. When everything is updated to only
            use a :class:`SessionMessage`, this should be removed.

        :param str name: Name of the experiment.
        :param str version: Version of the experiment.

        """
        self.send(ExperimentNameMessage(name))
        self.send(VersionMessage(version))
        self.send(SubjectIdMessage(subject))
        self.send(SessionMessage(name, version, subject, session))

    def send_math_message(self, problem, response, correct, response_time_ms,
                          timestamp):
        """Special callback to parse math events and send to the host PC.

        This is a slight hack that could be streamlined in a revamped PyEPL!

        :param str problem: Problem written as a string.
        :param str response: Entered response as a string.
        :param bool correct: Was the response the correct answer?
        :param int response_time_ms: Time before response was entered in ms.
        :param int timestamp: Event timestamp in ms.

        """
        self.send(MathMessage(problem, response, correct, response_time_ms,
                              timestamp=timestamp))

    def start_heartbeat(self):
        """Begin sending heartbeat messages to the host PC."""
        self.logger.info("Starting heartbeat...")
        addPollCallback(self.socket.send_heartbeat)

    def stop_heartbeat(self):
        """Stop sending heartbeat messages."""
        self.logger.info("Stopping heartbeat...")
        removePollCallback(self.socket.send_heartbeat)

    def align_clocks(self, poll_interval=1, callback=None):
        """Request the clock alignment procedure."""
        self._synced.clear()
        self.send(AlignClockMessage())
        while not self._synced:
            self.logger.debug("syncing...")
            self._synced.wait(poll_interval)
            if callback is not None:
                callback()

    def initiate_connection(self, poll_callback=default_connecting_callback,
                            poll_interval=1):
        """Wait for the host PC to connect. This blocks until the connection is
        established, but allows for a function to be called periodically while
        the connection has not yet been established.

        TODO: add actual ways to check for connection failure

        :param callable poll_callback: A function to run after no connection has
            been made for ``poll_interval`` seconds. TODO: can we do something
            more intelligent here?
        :param float poll_interval: Seconds to wait for a connection.
        :return: True if the connection succeeded
        :raises RamException:

        """
        if not self._configured:
            self.logger.error("Cannot connect before configuring")
            raise RamException("Unconfigured RAMControl")

        while not self._connected:
            time.sleep(poll_interval)
            if poll_callback is not None:
                poll_callback()

        # start actually checking connection
        self._last_heartbeat_received = time.time()

        # Send experiment info to host
        self.send(ExperimentNameMessage(self.experiment))
        self.send(VersionMessage(self.version))
        self.send(SessionMessage(self.session_num, ''))
        self.send(SubjectIdMessage(self.subject))
        self.start_heartbeat()

        self.logger.info("Connection succeeded.")
        return True

    def wait_for_start_message(self, poll_callback=None, interval=1):
        """Wait until ``START`` is received from the control PC.

        :param callable poll_callback:
        :param float interval: Polling interval in seconds.

        """
        if not self._connected:
            raise RamException("No connection to the host PC!")

        self.send(ReadyMessage())
        while not self._started:
            time.sleep(interval)
            if poll_callback is not None:
                poll_callback()

    def dispatch(self, msg):
        """Dispatch an incoming message to the appropriate handler.

        :param dict msg:

        """
        try:
            mtype = msg["type"]
        except KeyError:
            self.logger.error("No 'type' key in message!")
            return

        if mtype not in self.handlers:
            self.logger.error("Unknown message type %s received. Message=%s",
                              mtype, msg)
            return

        try:
            self.handlers[mtype](msg)
        except Exception as e:
            self.logger.error("Error handling message:\n%s", str(e))

    # Individual message handlers
    # -------------------------------------------------------------------------

    def id_handler(self, msg):
        """Handle ID messages."""
        self.logger.debug("I don't think this is ever used.")

    def sync_handler(self, msg):
        """Send SYNC pulses back to the host PC."""
        num = msg["num"]
        self.logger.info("Sync {} received".format(num))
        self.send(SyncMessage(num=num))

    def synced_handler(self, msg):
        """Receive notification that SYNC process was successful."""
        self.logger.info("Synchronization complete")
        self._synced.set()

    def exit_handler(self, msg):
        """Received exit from the host PC."""
        self.logger.info("RAMControl exiting")
        self.shutdown()

    def connected_handler(self, msg):
        """Indicate that we've made a connection."""
        self._connected = True
        self.socket.enqueue_message(ConnectedMessage())

    def heartbeat_handler(self, msg):
        """Received echoed heartbeat message from host."""
        self.logger.debug("Heartbeat returned.")
        self._last_heartbeat_received = time.time()

    def start_handler(self, msg):
        """Received START command."""
        self.logger.info("Got START")
        self._started = True

