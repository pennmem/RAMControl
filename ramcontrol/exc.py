class RamException(Exception):
    """Base exception class."""
RAMException = RamException


class WrongProcessError(RamException):
    """Raised when trying to call a method from the wrong process."""


class LanguageError(RamException):
    """Raised when a language is passed as an argument that is not available
    in a specific experiment.

    """


class ExperimentError(RamException):
    """Generic error raised in experiments."""


class VoiceServerError(RamException):
    """Raised when the voiceserver process had an issue."""


class MicTestAbort(RamException):
    """Raised when we should abort because of a mic test failure."""
