import logging


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
