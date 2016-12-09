import logging
from threading import Thread
import zmq
import json
from zmq.eventloop.ioloop import ZMQIOLoop
from zmq.eventloop.zmqstream import ZMQStream
from messages import RAMMessage

logger = logging.getLogger(__name__)


class SocketServer(Thread):
    """ZMQ-based socket server for sending and receiving messages from the host
    PC.

    :param zmq.Context ctx: ZMQ context. If None, a new one will be created.
    :param ZMQIOLoop loop: ZMQ event loop. If None, a new one will be created.
    :param str address: Address and port to bind to.

    """
    def __init__(self, ctx=None, loop=None, address="tcp://*:8889"):
        self.ctx = ctx or zmq.Context()
        self._loop = loop or ZMQIOLoop()
        self._recv_callback = self.default_callback

        self.address = address
        self._connected = False

        self.sock = self.ctx.socket(zmq.PAIR)
        # self.sock.setsockopt(zmq.LINGER, 0)  # discard messages that can't be sent
        self.stream = ZMQStream(self.sock, self._loop)
        self.stream.on_recv(self.on_recv)
        self.sock.bind(self.address)

        super(SocketServer, self).__init__()

    def register_recv_callback(self, callback):
        self._recv_callback = callback

    def default_callback(self, msg):
        logger.error("Message handling uninitialized! Msg {} received!".format(msg))

    @property
    def connected(self):
        return self._connected

    def on_recv(self, multipart):
        """Callback to handle incoming messages."""
        for string in multipart:
            logger.info("Incoming message: %s", string)

            try:
                msg = json.loads(string.decode())
                msg_type = msg["type"]
            except ValueError:
                logger.error("Unable to decode message. Is it JSON?")
                continue
            except KeyError:
                logger.error("Malformed message: missing 'type' key.")
                continue

            if msg_type == "SYNC":
                self.send(SyncMessage(msg["num"]))
            self._recv_callback(msg)
            logger.info("executing callback for %s message" % msg_type)

    def send(self, msg):
        """Transmit a message to the host PC.

        :param RAMMessage msg: Message to send.

        """
        out = msg.jsonize()
        logger.debug("Sending message: %s", out)
        try:
            self.stream.send(out, flags=zmq.NOBLOCK)
        except Exception as e:
            logger.error("Sending failed: {}", e)

    def wait_for_connection(self):
        logger.debug("Waiting to receive initialization json")
        logger.debug(self.sock.recv_json())  # Blocking
        logger.debug("Initialization json received")
        self._connected = True

    def stop(self):
        """Stop the event loop."""
        logger.info("Shutting down ZMQ event loop...")
        self._loop.stop()
        self._connected = False

    def run(self):
        """Starts event loop. Blocks"""
        self._loop.start()


if __name__ == "__main__":
    from messages import *

    logging.basicConfig(level=logging.DEBUG)

    server = SocketServer()
    logger.info("Awaiting connection...")
    logger.debug(server.sock.recv_json())

    logger.info("Sending ALIGNCLOCK...")
    server.send(AlignClockMessage())
    server.start()
    server.join()
