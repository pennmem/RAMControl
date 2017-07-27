import logging

_logger = logging.getLogger("ramupload")
_logger.addHandler(logging.NullHandler())

_handler = logging.FileHandler("upload.log")
_handler.setFormatter(logging.Formatter(
    fmt="[%(asctime)s] %(message)s"
))

upload_log = logging.getLogger("ramupload.uploadlog")
upload_log.addHandler(_handler)
