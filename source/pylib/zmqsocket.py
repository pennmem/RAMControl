import logging

import zmq
from zmq.eventloop.future import Context, Poller
from zmq.eventloop.ioloop import ZMQIOLoop
from tornado import gen
from tornado.locks import Event, Condition

from messages import RAMMessage, HeartbeatMessage
from exc import AlreadyRegisteredError

logger = logging.getLogger(__name__)


class SocketServer(object):
    """ZMQ-based socket server for sending and receiving messages from the host
    PC.

    :param zmq.Context ctx: ZMQ context. If None, a new one will be created.
    :param ZMQIOLoop loop: ZMQ event loop. If None, a new one will be created.
    :param str address: Address and port to bind to.

    """
    def __init__(self, ctx=None, loop=None, address="tcp://*:8889"):
        self.ctx = ctx or Context()
        self._loop = loop or ZMQIOLoop.current()

        self._connected = Condition()  # used to wait before sending heartbeats
        self._running = False
        self._quit = Event()  # signal coroutines to quit

        self._handlers = {
            "SYNC": lambda msg: self.send(SyncMessage(msg["num"]))
        }

        self.address = address

        self.sock = self.ctx.socket(zmq.PAIR)
        self.sock.bind(self.address)

    def register_handler(self, msg_type, func):
        """Register a message handler.

        :param str msg_type: The message type to handle.
        :param callable func: Handler function which takes the message as its
            only argument.

        """
        if msg_type in self._handlers:
            raise AlreadyRegisteredError("A handler is already registered for message type '%s'" % msg_type)

    def default_handler(self, msg):
        logger.error("Message handling uninitialized! Msg {} received!".format(msg))

    @property
    def connected(self):
        return self._running

    @gen.coroutine
    def send(self, msg):
        """Transmit a message to the host PC. This method is a coroutine.

        :param RAMMessage msg: Message to send.

        """
        out = msg.jsonize()
        logger.debug("Sending message: %s", out)
        try:
            yield self.sock.send(out)
        except Exception as e:
            logger.error("Sending failed: {}", e)

    @gen.coroutine
    def dispatch(self, msg):
        """Handle incoming message.

        :param dict msg:

        """
        if msg["type"] not in self._handlers:
            self.default_handler(msg)
        else:
            self._handlers[msg["type"]](msg)

    @gen.coroutine
    def _wait_for_connection(self):
        """Waits for the host PC to connect before allowing the normal message
        handling to proceed.

        """
        poller = Poller()
        poller.register(self.sock, zmq.POLLIN)
        done = False

        while not done:
            events = yield poller.poll(timeout=1000)

            if self.sock in dict(events):
                msg = yield self.sock.recv_json()
                logger.info("Incoming message: %s", msg)
                try:
                    if msg["type"] != "CONNECTED":
                        logger.error("Invalid message type: %s", msg["type"])
                    else:
                        self._connected.notify_all()
                        self._running = True
                        done = True
                except KeyError:
                    logger.error("Malformed message!")
            logger.debug("Awaiting connection...")

    @gen.coroutine
    def _heartbeater(self):
        """Coroutine for sending heartbeats."""
        yield self._connected.wait()

        while not self._quit.is_set():
            yield self.send(HeartbeatMessage())
            yield gen.sleep(1)

    @gen.coroutine
    def _listen(self):
        """Listen for messages on the socket and handle appropriately."""
        yield self._connected.wait()

        poller = Poller()
        poller.register(self.sock, zmq.POLLIN)

        while not self._quit.is_set():
            events = yield poller.poll(timeout=1000)

            if self.sock in dict(events):
                incoming = yield self.sock.recv_multipart()
                for msg in incoming:
                    logger.info("Incoming message: %s", msg)

                    try:
                        message = json.loads(msg.decode())
                    except Exception as e:
                        logger.error("Unable to decode JSON.\n%s", str(e))
                        continue

                    yield self.dispatch(message)

    @gen.coroutine
    def _coroutine_runner(self):
        """Executes all long-running coroutines."""
        yield [self._wait_for_connection(), self._heartbeater(), self._listen()]

    def wait_for_connection(self):
        logger.debug("Waiting to receive initialization json")
        logger.debug(self.sock.recv_json())  # Blocking
        logger.debug("Initialization json received")
        self._connected = True

    def stop(self):
        """Stop the event loop."""
        logger.info("Shutting down ZMQ event loop...")
        self._running = False
        self._quit.set()

    def start(self):
        """Starts event loop. Blocks"""
        self._loop.run_sync(self._coroutine_runner)


if __name__ == "__main__":
    from messages import *

    logging.basicConfig(level=logging.DEBUG)

    server = SocketServer()
    logger.info("Awaiting connection...")
    server.start()
