"""Interfaces to the Control PC"""

from threading import Thread, Event
import logging

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty

from pyepl.locals import *
from pyepl.locals import Text

from zmqsocket import SocketServer
from exc import RamException
from messages import *

logger = logging.getLogger(__name__)


def default_attempt_callback():
    flashStimulus(Text("Searching for Control PC"), 800)


def default_connecting_callback():
    try:
        flashStimulus(Text("Connecting to Control PC"), 800)
    except AttributeError:
        logger.info("Connecting to control PC")


def default_success_callback():
    flashStimulus(Text("Connection established"), 800)


def default_failure_callback():
    flashStimulus(Text("Connection failed"), 800)


class RAMControl(object):
    """Main controller for running RAM task laptop tasks.

    Process::

        control = RAMControl.instance()  # gets singleton
        control.initialize()
        control.connect_to_host # blocks

    """
    DEFAULT_HEARTBEAT_INTERVAL = 1000  # ms
    MAX_QUEUE_SIZE = 32
    _instance = None

    def __init__(self, address="tcp://192.168.137.200:8889"):
        if self._instance is not None:
            raise Exception("Multiple RAM instances requested!")

        self._initialized = False
        self._synced = Event()
        self._configured = False
        self._connection_failed = False
        self._quit = Event()

        # Experiment-specific data to be filled in later
        self.experiment = ''
        self.version = ''
        self.session_num = -1
        self.session_type = ''
        self.subject = ''
        self.allowed_states = []

        # Configure basic message handlers
        self.handlers = {
            "ID": self.id_handler,
            "SYNC": self.sync_handler,
            "SYNCED": self.synced_handler,
            "EXIT": self.exit_handler,
            "HEARTBEAT": self.heartbeat_handler
        }

        self.socket = SocketServer()
        self.socket.register_handler(self.dispatch)
        self.socket.bind(address)
        self._socket_thread = Thread(target=self.socket.start)

    @classmethod
    def instance(cls, *args, **kwargs):
        """Return the singleton :class:`RAMControl` instance."""
        if cls._instance is None:
            cls._instance = RAMControl(*args, **kwargs)
        return cls._instance

    @property
    def synced(self):
        return self._synced.is_set()

    @property
    def network_connected(self):
        return self.socket.connected

    @staticmethod
    def get_system_time_in_micros():
        """Convenience method to return the system time."""
        return time.time() * 1000000.0

    @staticmethod
    def get_system_time_in_millis():
        """Convenience method to return the system time."""
        return int(round(time.time() * 1000.0))

    @staticmethod
    def build_message(msg_type, timestamp=None, *args, **kwargs):
        """Build and return a RAMMessage to be sent to control PC."""
        return get_message_type(msg_type)(*args, timestamp=timestamp, **kwargs)

    def register_handler(self, name, func):
        """Register a message handler.

        :param str name: Message type to handle.
        :param callable func: Function to call.

        """
        self.handlers[name] = func

    def configure(self, experiment, version, session_num, session_type, subject, states):
        """Set various experiment options so they can be transmitted to the host
        PC.

        :param str experiment:
        :param version:
        :param session_num:
        :param str session_type:
        :param str subject:
        :param list states: Allowed states

        """
        self.experiment = experiment
        self.version = version
        self.session_num = session_num
        self.session_type = session_type
        self.subject = subject
        self.allowed_states = states
        self._configured = True

    def send(self, message):
        """Send a message to the host PC."""
        if not isinstance(message, RAMMessage):
            logger.error("Cannot send non-RamMessage! Returning!")
        else:
            self.socket.enqueue_message(message)

    def align_clocks(self, poll_interval=1, callback=None):
        """Request the clock alignment procedure."""
        self._synced.clear()
        self.send(AlignClockMessage())
        while not self._synced:
            logger.debug("syncing...")
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
            logger.error("Cannot connect before configuring")
            raise RamException("Unconfigured RAMControl")

        self._socket_thread.start()

        while not self.socket.connected:
            time.sleep(poll_interval)
            if poll_callback is not None:
                poll_callback()

        # Send experiment info to host
        self.send(ExperimentNameMessage(self.experiment))
        self.send(VersionMessage(self.version))
        self.send(SessionMessage(self.session_num, self.session_type))
        self.send(SubjectIdMessage(self.subject))
        self.send(DefineMessage(self.allowed_states))

        logger.info("Connection succeeded.")
        return True

    def dispatch(self, msg):
        """Dispatch an incoming message to the appropriate handler.

        :param dict msg:

        """
        try:
            mtype = msg["type"]
        except KeyError:
            logger.error("No 'type' key in message!")
            return

        if mtype not in self.handlers:
            logger.error("Unknown message type %s received. Message=%s", mtype, msg)
            return

        try:
            self.handlers[mtype](msg)
        except Exception as e:
            logger.error("Error handling message:\n%s", str(e))

    # Individual message handlers
    # -------------------------------------------------------------------------

    def id_handler(self, msg):
        """Handle ID messages."""
        logger.debug("I don't think this is ever used.")

    def sync_handler(self, msg):
        """Send SYNC pulses back to the host PC."""
        num = msg["num"]
        logger.error("Sync {} received".format(num))
        self.send(SyncMessage(num=num))

    def synced_handler(self, msg):
        """Receive notification that SYNC process was successful."""
        logger.info("Synchronization complete")
        self._synced.set()

    def exit_handler(self, msg):
        """Received exit from the host PC."""
        logger.info("RAMControl exiting")
        self.send(ExitMessage())
        self.socket.stop()
        self._quit.set()

    def heartbeat_handler(self, msg):
        """Received echoed heartbeat message from host."""
        logger.info("Heartbeat returned.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    ram_control = RAMControl.instance()

    ram_control.configure("", 1, 1, "", "me", [])
    ram_control.initiate_connection()
