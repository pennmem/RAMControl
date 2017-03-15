import logging
from logging.handlers import RotatingFileHandler, DatagramHandler
from socket import socket, AF_INET, SOCK_DGRAM
from six.moves import socketserver, cPickle as pickle
from six.moves.queue import Queue
from threading import Thread
from multiprocessing import Process

DEFAULT_LOG_PORT = 9123


class LogHandler(socketserver.DatagramRequestHandler):
    def handle(self):
        try:
            # It is mostly undocumented, but there are 4 bytes which give the
            # length of the pickled LogRecord.
            _ = self.rfile.read(4)
            msg = self.rfile.read()
            LogServer.queue.put(logging.makeLogRecord(pickle.loads(msg)))
        except:
            print("Error reading log record!")


class LogServer(socketserver.ThreadingUDPServer):
    """Centralized server for handling logging to files."""
    filename = "logs.log"
    queue = Queue()

    def consume(self):
        while True:
            record = self.queue.get()
            print({
                "timestamp": record.created,
                "name": record.name,
                "levelname": record.levelname,
                "pathname": record.pathname,
                "lineno": record.lineno,
                "threadName": record.threadName,
                "processName": record.processName,
                "msg": record.msg
            })

    @staticmethod
    def run(host, port, filename=None):
        """Run a :class:`LogServer` instance.

        :param str host: Address string.
        :param int port: Port number.
        :param str filename: Base filename for logs.

        """
        consumer = LogServer((host, port), LogHandler)
        if filename is not None:
            consumer.filename = filename
        consume_thread = Thread(target=consumer.consume)
        consume_thread.daemon = True
        consume_thread.start()
        consumer.serve_forever()


def create_logger(name, host="127.0.0.1", port=DEFAULT_LOG_PORT):
    """Create a logger and setup appropriately. For loggers running outside of
    the main process, this must be called after the process has been started
    (i.e., in the :func:`run` method of a :class:`multiprocessing.Process`
    instance).

    :param str name: Name of the logger.
    :param str host: Host address.
    :param int port: UDP port.

    """
    logger = logging.getLogger(name)
    logger.addHandler(logging.StreamHandler())
    logger.addHandler(DatagramHandler(host, port))
    return logger


def setup_logging(fmt="[%(levelname)1.1s %(asctime)s] %(pathname)s:%(lineno)d\n%(message)s\n",
                  datefmt=None, name=None, level=logging.INFO, handlers=[]):
    """Configure RAM logging output.

    :param str fmt: Log format to use (passed to :func:`logging.Formatter`)
    :param str datefmt: Timestamp format (passed to :func:`logging.Formatter`)
    :param str name: Logger name to configure for (default: ``None``)
    :param int level: Minimum log level to log
    :param list handlers: List of additional handlers to use.

    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(fmt, datefmt=datefmt)
    if len(logger.handlers) == 0:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)


if __name__ == "__main__":
    import random
    import string
    import time

    def log_producer():
        logger = create_logger(random.choice(string.ascii_lowercase))
        for _ in range(1):
            n = random.randint(0, 10)
            logger.info("hi %d", n)
            logger.warning("hi %d", n)
            logger.error("hi %d", n)
            logger.critical("hi %d", n)
            logger.debug("hi %d", n)
            time.sleep(random.randint(1, 3))

    server = Process(target=LogServer.run, args=("127.0.0.1", DEFAULT_LOG_PORT))
    server.start()

    procs = [Process(target=log_producer) for _ in range(1)]

    for proc in procs:
        proc.start()
    proc.join()
    server.terminate()
