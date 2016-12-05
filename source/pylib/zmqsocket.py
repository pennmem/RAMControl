import logging
from threading import Thread
import zmq
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
    def __init__(self, ctx=None, loop=None, address="tcp://192.168.137.200:8889"):
        self.ctx = ctx or zmq.Context()
        self._loop = loop or ZMQIOLoop()

        self.address = address
        self.connected = False

        self.sock = self.ctx.socket(zmq.PAIR)
        # self.sock.setsockopt(zmq.LINGER, 0)  # discard messages that can't be sent
        self.stream = ZMQStream(self.sock, self._loop)
        self.stream.on_recv(self.on_recv)
        self.sock.bind(self.address)

        super(SocketServer, self).__init__()

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
            else:
                logger.info("doing nothing on %s message" % msg_type)

    def send(self, msg):
        """Transmit a message to the host PC.

        :param RAMMessage msg: Message to send.

        """
        out = msg.jsonize()
        logger.debug("Sending message: %s", out)
        try:
            self.stream.send(out, flags=zmq.NOBLOCK)
        except Exception as e:
            print(e)

    def stop(self):
        """Stop the event loop."""
        logger.info("Shutting down ZMQ event loop...")
        self._loop.stop()

    def run(self):
        self._loop.start()


if __name__ == "__main__":
    import time
    from threading import Timer
    from messages import *

    logging.basicConfig(level=logging.DEBUG)

    server = SocketServer()
    logger.info("Awaiting connection...")
    logger.debug(server.sock.recv_json())

    logger.info("Sending ALIGNCLOCK...")
    server.send(AlignClockMessage())
    server.start()
    server.join()
