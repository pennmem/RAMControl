"""Messages for communicating with the host PC."""

import sys
import json
import time
import inspect


class RAMMessage(object):
    """Base message class.

    :param event_type: The type of event.
    :param timestamp: Event timestamp in ms.
    :param data: Data associated with the event.
    :param aux_data: Additional data associated with the event.

    """
    def __init__(self, event_type, timestamp=None, data=None, aux_data=None):
        self.event_type = event_type
        self.timestamp = timestamp or self.now()
        self.data = data
        self.aux_data = aux_data

    def __str__(self):
        return self.event_type

    def jsonize(self):
        """Serialize the message to JSON."""
        return json.dumps(self.to_dict())

    def to_dict(self):
        """Convert to a dict."""
        return {
            "time": self.timestamp,
            "type": self.event_type,
            "data": self.data,
            "aux": self.aux_data
        }

    @staticmethod
    def now():
        """Return the current time in ms."""
        return time.time() * 1000


class ConnectedMessage(RAMMessage):
    """Message indicating that a new socket connection has been established."""
    def __init__(self, timestamp=None):
        super(ConnectedMessage, self).__init__("CONNECTED", timestamp=timestamp)


class HeartbeatMessage(RAMMessage):
    """Heartbeat message to check on both ends if the network connection is
    still alive.

    """
    def __init__(self, interval=1, timestamp=None):
        super(HeartbeatMessage, self).__init__("HEARTBEAT", timestamp=timestamp, data=interval)


class ExperimentNameMessage(RAMMessage):
    """Transmit the name of the current experiment."""
    def __init__(self, experiment, timestamp=None):
        super(ExperimentNameMessage, self).__init__("EXPNAME", timestamp=timestamp, data=experiment)


class VersionMessage(RAMMessage):
    """Communicates the software version number."""
    def __init__(self, version, timestamp=None):
        super(VersionMessage, self).__init__("VERSION", timestamp=timestamp, data=version)


class SessionMessage(RAMMessage):
    """Transmit information about the current session."""
    def __init__(self, session, session_type, timestamp=None):
        data = {
            "session_type": session_type,
            "session_number": session
        }
        super(SessionMessage, self).__init__("SESSION", timestamp=timestamp, data=data)


class SubjectIdMessage(RAMMessage):
    """Send subject ID."""
    def __init__(self, subject, timestamp=None):
        super(SubjectIdMessage, self).__init__("SUBJECTID", timestamp=timestamp, data=subject)


class AlignClockMessage(RAMMessage):
    """Request running the clock alignment procedure."""
    def __init__(self, timestamp=None):
        super(AlignClockMessage, self).__init__("ALIGNCLOCK", timestamp=timestamp)


class SyncMessage(RAMMessage):
    """Used for determining network latency."""
    def __init__(self, num, timestamp=None):
        super(SyncMessage, self).__init__("SYNC", timestamp=timestamp, aux_data=num)


class DefineMessage(RAMMessage):
    """Sends a DEFINE message. Whatever that means."""
    def __init__(self, states, timestamp=None):
        super(DefineMessage, self).__init__("DEFINE", timestamp=timestamp, data=states)


class ExitMessage(RAMMessage):
    """Sends an EXIT message."""
    def __init__(self, timestamp=None):
        super(ExitMessage, self).__init__("EXIT", timestamp=timestamp)


class StateMessage(RAMMessage):
    def __init__(self, state, value, timestamp=None, meta=None):
        data = dict(name=state, value=value)
        if meta is not None and state == "WORD":
            data["word"] = meta
        super(StateMessage, self).__init__("STATE", data=data, timestamp=timestamp)


class TrialMessage(RAMMessage):
    def __init__(self, trial, timestamp=None):
        super(TrialMessage, self).__init__("TRIAL", data=dict(trial=trial), timestamp=timestamp)


class ReadyMessage(RAMMessage):
    """Sent when waiting for the start button to be pressed on the control PC.

    """
    def __init__(self, timestamp=None):
        super(ReadyMessage, self).__init__("READY", timestamp=timestamp)


class WordMessage(RAMMessage):
    """Inform the host PC that a new word is being displayed."""
    def __init__(self, word, timestamp=None):
        super(WordMessage, self).__init__("WORD", data=word, timestamp=timestamp)


class MathMessage(RAMMessage):
    """Sends information about math events."""
    def __init__(self, problem, response, correct, response_time_ms, timestamp=None):
        payload = {
            "problem": problem,
            "response": response,
            "correct": correct,
            "response_time_ms": response_time_ms
        }
        super(MathMessage, self).__init__("MATH", timestamp=timestamp, data=payload)


_mod = sys.modules[__name__]
_names = dir(_mod)
message_types = {
    name.split("Message")[0].upper(): getattr(_mod, name)
    for name in _names
    if inspect.isclass(getattr(_mod, name))
    and name is not "RAMMessage"
    and name is not "ExperimentNameMessage"  # this is named differently than the message
}
message_types["EXPNAME"] = ExperimentNameMessage


def get_message_type(kind):
    """Return the message class. Used to build messages."""
    if kind in message_types:
        return message_types[kind]
    raise Exception("No applicable message type {}", kind) # TODO: ???


if __name__ == "__main__":
    print(sorted(message_types.keys()))
