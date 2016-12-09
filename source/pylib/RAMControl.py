"""
Interfaces to the Control PC
"""

from threading import Thread, Event
from collections import defaultdict
import logging

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

from zmqsocket import SocketServer
from pyepl.locals import *
from messages import *
from pyepl.locals import Text

logger = logging.getLogger(__name__)


def default_attempt_callback():
    flashStimulus(Text("Searching for Control PC"), 800)


def default_connecting_callback():
    flashStimulus(Text("Connecting to Control PC"), 800)


def default_success_callback():
    flashStimulus(Text("Connection established"), 800)


def default_failure_callback():
    flashStimulus(Text("Connection failed"), 800)


class _RAMControl(object):
    """
    Process:
    control = ram_control # gets signleton
    control.initialize()
    control.gonnect_to_host # blocks

    """

    CLS_INITIALIZED = False
    DEFAULT_HEARTBEAT_INTERVAL = 1000  # ms
    MAX_QUEUE_SIZE = 32

    def __init__(self):
        """Do not instantiate RAMControl directly, but use ram_control instance variable"""
        if self.CLS_INITIALIZED:
            raise Exception("Multiple RAM instances requested!")
        self.CLS_INITIALIZED = True

        self.socket = None  # SocketServer()

        self._heart_beating = False
        self.heartbeat_interval = self.DEFAULT_HEARTBEAT_INTERVAL
        self.heartbeat_thread = Thread(target=self._heartbeat)
        self.message_process_thread = Thread(target=self._process_messages)

        self.message_queue = Queue(maxsize=self.MAX_QUEUE_SIZE)
        self.n_queued_messages = 0
        self.callbacks = defaultdict(list)

        self.receive_thread = Thread(target=self._start_receive)
        self._initialized = False
        self._synced = Event()
        self._configured = False
        self._connection_failed = False

        self.experiment = ''
        self.version = ''
        self.session_num = -1
        self.session_type = ''
        self.subject = ''
        self.allowed_states = []

        self.add_message_callbacks(
            ID=self._callback_id,
            SYNC=self._callback_sync,
            SYNCED=self._callback_synced,
            EXIT=self._callback_exit
        )

    def add_message_callbacks(self, **kwargs):
        for key, callback in kwargs.items():
            self.callbacks[key].append(callback)

    @property
    def synced(self):
        return self._synced.is_set

    @property
    def initialized(self):
        return self._initialized

    @property
    def is_receiving(self):
        return self.receive_thread.is_alive if self.receive_thread else False

    @property
    def network_connected(self):
        return self.socket.connected if self.socket else False

    @staticmethod
    def get_system_time_in_micros():
        """Convenience method to return the system time."""
        return time.time() * 1000000.0

    @staticmethod
    def get_system_time_in_millis():
        """Convenience method to return the system time."""
        return int(round(time.time() * 1000.0))

    def initialize(self, address="tcp://192.168.137.200:8889"):
        if self.initialized:
            logger.warning("Attempted multiple initializations")
            return
        self._synced.clear()
        self._initialized = True
        self.socket = SocketServer(address=address)
        self.socket.register_recv_callback(self._receipt_callback)

    def _start_receive(self):
        self.receive_thread = Thread(target=self.socket.run)
        logger.debug("Starting receiving thread")
        self.receive_thread.start()
        logger.debug("Starting message processing thread")
        self.message_process_thread.start()

    def join(self):
        if self.receive_thread.is_alive:
            logger.debug("Waiting for receive thread to finish")
            self.receive_thread.join()
        if self.message_process_thread.is_alive:
            logger.debug("Waiting for process thread to finish")
            self.message_process_thread.join()

    def _stop_receive(self):
        self.socket.stop()
        if self.receive_thread.is_alive:
            self.receive_thread.join()

    def _receipt_callback(self, message):
        self.message_queue.put(message)

    def _process_messages(self):
        while self.network_connected or not self.message_queue.empty():

            try:
                message = self.message_queue.get(block=True, timeout=1)
                logger.debug("none")
            except Empty:
                continue

            logger.debug("Message {} dequeued".format(message))

            if not isinstance(message, dict):
                logger.error("Non-dictionary message received. Message={}".format(message))
                return
            if message['type'] not in self.callbacks:
                logger.error("Unknown message type {} received. Message={}".format(message['type'], message))
                return

            for callback in self.callbacks[message['type']]:
                try:
                    logger.debug('{} received'.format(message))
                    callback(message)
                except Exception as e:
                    logger.error("Exception {} received executing callback {} for {}".format(e, callback, message))

    def _callback_id(self, msg):
        logger.debug("I don't think this is ever used.")

    def _callback_sync(self, msg):
        logger.error("Sync {} received".format(msg['num']))

    def _callback_synced(self, msg):
        logger.info("Synchronization complete")
        self._synced.set()

    def _callback_exit(self, msg):
        logger.info("RAMControl exiting")
        self.send(ExitMessage())
        self.disconnect()

    def align_clocks(self, poll_interval=1, callback=None):
        self._synced.clear()
        self.send(AlignClockMessage())
        while not self._synced:
            logger.debug("syncing...")
            self._synced.wait(poll_interval)
            if callback:
                callback()

    def send(self, message):
        """
        This blocks until the message is sent.  Returns the total number of characters sent to control PC
        """
        if not isinstance(message, RAMMessage):
            logger.error("Cannot send non-RamMessage! Returning!")
            return
        self.socket.send(message)

    @staticmethod
    def build_message(msg_type, timestamp=None, *args, **kwargs):
        """Build and return a RAMMessage to be sent to control PC.

        """
        return get_message_type(msg_type)(*args, timestamp=timestamp, **kwargs)

    def _wait_for_connection(self):
        logger.info("Initiating socket...")
        self.socket.wait_for_connection()
        logger.info("Connection established")

    def configure(self, experiment, version, session_num, session_type, subject, states):
        self.experiment = experiment
        self.version = version
        self.session_num = session_num
        self.session_type = session_type
        self.subject = subject
        self.allowed_states = states
        self._configured = True

    def _connect_to_host(self):
        self._connection_failed = False
        if not self._configured:
            logger.warning("Cannot connect before configuring")
            raise Exception("Unconfigured RAMControl")
        if not self.initialized:
            logger.debug("Auto initializing")
            try:
                self.initialize()
            except Exception as e:
                self._connection_failed = True
                raise
        self._wait_for_connection()
        if not self.network_connected:
            self._connection_failed = True
            raise Exception("Could not connect to host PC")
        self._start_receive()
        self.send(ExperimentNameMessage(self.experiment))
        self.send(VersionMessage(self.version))
        self.send(SessionMessage(self.session_num, self.session_type))
        self.send(SubjectIdMessage(self.subject))
        self.send(DefineMessage(self.allowed_states))
        self._start_heartbeat()

    def _start_heartbeat(self):
        self._heart_beating = True
        self.heartbeat_thread.start()

    def _stop_heartbeat(self):
        self._heart_beating = False
        if self.heartbeat_thread.is_alive:
            self.heartbeat_thread.join()

    def _heartbeat(self):
        while self._heart_beating:
            self.send(HeartbeatMessage(self.heartbeat_interval))
            time.sleep(self.heartbeat_interval/1000.)

    def disconnect(self):
        """
        Disconnect and close the connection to the Control PC.
        """
        self._stop_heartbeat()
        self._stop_receive()

    def initiate_connection(self, poll_interval=1):
        connection_thread = Thread(target=self._connect_to_host)
        connection_thread.start()

        while not self.network_connected and not self._connection_failed:
            logger.info("Attempting connection...")
            time.sleep(poll_interval)

        if self._connection_failed:
            logger.error("Connection failed.")
            return False

        while not self._heart_beating and not self._connection_failed:
            logger.info("Connecting...")
            time.sleep(poll_interval)

        connection_thread.join()

        if not self._connection_failed:
            logger.info("Connection succeeded.")
        else:
            logger.error("Connection failed.")
        return not self._connection_failed

ram_control = _RAMControl()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    ram_control.configure("", 1, 1, "", "me", [])
    ram_control.initiate_connection()
    ram_control.join()
