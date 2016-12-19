import logging
import time

try:
    from queue import Queue
except ImportError:
    from Queue import Queue

import zmq

from messages import RAMMessage, HeartbeatMessage

logger = logging.getLogger(__name__)


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
        logger.debug("Adding handler: %s", func.__name__)
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
            logger.debug("Sending message: %s", out)
            self.sock.send(out)
        except Exception as e:
            logger.error("Sending failed: {}", e)

    def send_heartbeat(self):
        """Convenience method to send a heartbeat message to the host PC."""
        if time.time() - self._last_heartbeat >= 1.0:
            self.send(HeartbeatMessage())
            self._last_heartbeat = time.time()

    def _handle_incoming(self):
        events = self.poller.poll(1)
        if self.sock in dict(events):
            try:
                msg = self.sock.recv_json()
            except:
                logger.error("Unable to decode JSON.", exc_info=True)
                return

            logger.info("Incoming message: %s", msg)

            for handler in self._handlers:
                try:
                    handler(msg)
                except:
                    logger.error("Error handling message", exc_info=True)
                    continue

    def _handle_outgoing(self):
        try:
            while not self._out_queue.empty():
                msg = self._out_queue.get_nowait()
                self.send(msg)
        except:
            logger.error("Error in outgoing message processing", exc_info=True)

    def update(self):
        """Call periodically to check for incoming messages and/or send messages
        in the outgoing queue.

        """
        self._handle_incoming()
        self._handle_outgoing()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    server = SocketServer()
    server.bind()
