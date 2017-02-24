"""Exception types."""

class RamException(Exception):
    """Base exception class."""
RAMException = RamException


class WrongProcessError(RamException):
    """Raised when trying to call a method from the wrong process."""
