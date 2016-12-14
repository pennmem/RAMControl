import logging
import json

import zmq
from zmq.eventloop.future import Context, Poller
from zmq.eventloop.ioloop import ZMQIOLoop
from tornado import gen
from tornado.queues import Queue
from tornado.locks import Event, Condition

from messages import RAMMessage, HeartbeatMessage
from exc import RamException

logger = logging.getLogger(__name__)


class SocketServer(object):
    """ZMQ-based socket server for sending and receiving messages from the host
    PC.

    :param zmq.Context ctx: ZMQ context. If None, a new one will be created.
    :param ZMQIOLoop loop: ZMQ event loop. If None, a new one will be created.

    """
    def __init__(self, ctx=None, loop=None):
        self.ctx = ctx or Context()
        self._loop = loop or ZMQIOLoop.current()

        self._connected = Condition()  # used to wait before sending heartbeats
        self._running = False
        self._quit = Event()  # signal coroutines to quit

        self._handlers = []

        self.sock = self.ctx.socket(zmq.PAIR)
        self._bound = False

        # Outgoing message queue
        self._out_queue = Queue()

    @property
    def connected(self):
        return self._running

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

    @gen.coroutine
    def send(self, msg):
        """Transmit a message to the host PC. This method is a coroutine.

        :param RAMMessage msg: Message to send.

        """
        out = msg.jsonize()
        try:
            logger.debug("Sending message: %s", out)
            yield self.sock.send(out)
        except Exception as e:
            logger.error("Sending failed: {}", e)

    @gen.coroutine
    def _wait_for_connection(self):
        """Waits for the host PC to connect before allowing the normal message
        handling to proceed.

        """
        poller = Poller()
        poller.register(self.sock, zmq.POLLIN)
        done = False
        wait_time = 1
        elapsed = 0

        while not done:
            events = yield poller.poll(timeout=wait_time*1000)
            elapsed += wait_time

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
            logger.info("No connection yet (%d s since starting)...", elapsed)

    @gen.coroutine
    def _heartbeater(self):
        """Coroutine for sending heartbeats."""
        yield self._connected.wait()

        while not self._quit.is_set():
            yield self.send(HeartbeatMessage(interval=1))
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

                    # TODO: better way to run handlers in the background or as coroutines?
                    for handler in self._handlers:
                        handler(message)
                        yield gen.moment  # allow other coroutines to run before running next handler

    @gen.coroutine
    def _pop_and_send(self):
        """Coroutine for sending messages from the queue."""
        while not self._quit.is_set():
            msg = yield self._out_queue.get()
            yield self.send(msg)

    @gen.coroutine
    def _coroutine_runner(self):
        """Executes all long-running coroutines."""
        yield [
            self._wait_for_connection(),
            self._heartbeater(),
            self._listen(),
            self._pop_and_send()
        ]

    def stop(self):
        """Stop the event loop."""
        logger.info("Shutting down ZMQ event loop...")
        self._running = False
        self._quit.set()

    def start(self):
        """Starts event loop. Blocks"""
        if not self._bound:
            raise RamException("You must bind the socket first!")
        self._loop.run_sync(self._coroutine_runner)  # blocks
        self.sock.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    server = SocketServer()
    server.bind()
    logger.info("Awaiting connection...")
    server.start()
