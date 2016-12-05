"""Messages for communicating with the host PC."""

import json
import time


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

    def jsonize(self):
        """Serialize the message to JSON."""
        return json.dumps({
            "time": self.timestamp,
            "type": self.event_type,
            "data": self.data,
            "aux": self.aux_data
        })

    @staticmethod
    def now():
        """Return the current time in ms."""
        return time.time() * 1000


class HeartbeatMessage(RAMMessage):
    """Heartbeat message to check on both ends if the network connection is
    still alive.

    """
    def __init__(self, interval, timestamp=None):
        super(HeartbeatMessage, self).__init__("HEARTBEAT", timestamp=timestamp, data=interval)


class ExperimentNameMessage(RAMMessage):
    """Transmit the name of the current experiment."""
    def __init__(self, name):
        super(ExperimentNameMessage, self).__init__("EXPNAME", data=name)


class VersionMessage(RAMMessage):
    """Communicates the software version number."""
    def __init__(self, version):
        super(VersionMessage, self).__init__("VERSION_NUM", data=version)


class SessionMessage(RAMMessage):
    """Transmit information about the current session."""
    def __init__(self, stype, snum):
        data = {
            "session_type": stype,
            "session_number": snum
        }
        super(SessionMessage, self).__init__("SESSION", data=data)


class SubjectIdMessage(RAMMessage):
    """Send subject ID."""
    def __init__(self, subject):
        super(SubjectIdMessage, self).__init__("SUBJECTID", data=subject)


class AlignClockMessage(RAMMessage):
    """Request running the clock alignment procedure."""
    def __init__(self):
        super(AlignClockMessage, self).__init__("ALIGNCLOCK")


class SyncMessage(RAMMessage):
    """Used for determining network latency."""
    def __init__(self, num):
        super(SyncMessage, self).__init__("SYNC", aux_data=num)


class DefineMessage(RAMMessage):
    """Sends a DEFINE message. Whatever that means."""
    def __init__(self):
        super(DefineMessage, self).__init__("DEFINE")
