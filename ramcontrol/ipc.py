import time
import traceback as tb


def message(message_type, data=None):
    """Return a dict to communicate between processes.

    :param str message_type: Type of the message.
    :param data: Picklable data to send along with the message if any.

    """
    return {
        "type": message_type,
        "data": data,
        "created": time.time()
    }


def critical_error_message(comment):
    """Convenience function to create a message of type ``CRITICAL``."""
    return message("CRITICAL", dict(msg=comment, traceback=tb.format_exc()))
