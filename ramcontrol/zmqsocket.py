import time
import json
from six.moves.queue import Queue

import zmq
from logserver import create_logger

from messages import RAMMessage, HeartbeatMessage


class SocketServer(object):
    """ZMQ-based socket server for sending and receiving messages from the host
    PC.

    Because of the weird way in which PyEPL handles events, we can't run this as
    its own thread, but instead have to poll for events in the general PyEPL
    machinery. In the future, we should clean up PyEPL entirely so that it does
    not block other threads (amongst other reasons).

    :param zmq.Context ctx:

    """
    def __init__(self, ctx=None):
        self.ctx = ctx or zmq.Context()

        self._handlers = []

        self.sock = self.ctx.socket(zmq.PAIR)
        self._bound = False

        self.poller = zmq.Poller()
        self.poller.register(self.sock, zmq.POLLIN)

        # Outgoing message queue
        self._out_queue = Queue()

        # time of last sent heartbeat message
        self._last_heartbeat = 0.

        # Logging of sent and received messages.
        self.logger = create_logger(__name__)

    def join(self):
        """Block until all outgoing messages have been processed."""
        self.logger.warning("This doesn't work yet...")
        # self._out_queue.join()

    def bind(self, address="tcp://*:8889"):
        """Bind the socket to start listening for connections.

        :param str address: ZMQ address string

        """
        self.sock.bind(address)
        self._bound = True

    def register_handler(self, func):
        """Register a message handler.

        :param callable func: Handler function which takes the message as its
            only argument.

        """
        self.logger.debug("Adding handler: %s", func.__name__)
        self._handlers.append(func)

    def enqueue_message(self, msg):
        """Submit a new outgoing message to the queue."""
        self._out_queue.put_nowait(msg)

    def send(self, msg):
        """Immediately transmit a message to the host PC. It is advisable to not
        call this method directly in most cases, but rather enqueue a message to
        be sent via :meth:`enqueue_message`.

        :param RAMMessage msg: Message to send.

        """
        out = msg.jsonize()
        try:
            self.logger.debug("Sending message: %s", out)
            try:
                self.sock.send(out, zmq.NOBLOCK)
            except:
                pass
        except Exception:
            self.logger.error("Sending failed!", exc_info=True)

    def send_heartbeat(self):
        """Convenience method to send a heartbeat message to the host PC."""
        if time.time() - self._last_heartbeat >= 1.0:
            self.send(HeartbeatMessage())
            self._last_heartbeat = time.time()

    def log_message(self, message, incoming=True):
        """Log a message to the log file."""
        if not incoming:
            message = message.to_dict()

        message["in_or_out"] = "in" if incoming else "out"
        self.logger.info("%s", json.dumps(message))

    def handle_incoming(self):
        events = self.poller.poll(1)
        if self.sock in dict(events):
            try:
                msg = self.sock.recv_json()
                self.log_message(msg, incoming=True)
            except:
                self.logger.error("Unable to decode JSON.", exc_info=True)
                return

            for handler in self._handlers:
                try:
                    handler(msg)
                except:
                    self.logger.error("Error handling message", exc_info=True)
                    continue

    def handle_outgoing(self):
        try:
            while not self._out_queue.empty():
                msg = self._out_queue.get_nowait()
                self.send(msg)
                self._out_queue.task_done()  # so we can join the queue elsewhere
                self.log_message(msg, incoming=False)
        except:
            self.logger.error("Error in outgoing message processing",
                              exc_info=True)

    def update(self):
        """Call periodically to check for incoming messages and/or send messages
        in the outgoing queue.

        """
        self.handle_incoming()
        self.handle_outgoing()

