"""
Interfaces to the Control PC
"""
import re
import select
import json
from time import time, sleep
import logging
try:
    from queue import Queue
except ImportError:
    from Queue import Queue

from Network import Network
from pyepl.hardware import addPollCallback, removePollCallback
from pyepl.locals import *

logger = logging.getLogger(__name__)


class RAMControl(object):
    JSON_SPLITTER = re.compile(
        '(?<=})\s*{')  # REGEXP to split consecutive JSON message
    # NOTE: Removes leading brace of all but the first message

    QUEUE_SIZE = 20  # Blocks if the queue is full

    # Use getInstance() to instantiate this class
    singleton_instance = None

    def __init__(self):
        """Do not instantiate RAMControl directly, but use getInstance instead."""
        self.network = None  # Network class instance
        self.isHeartbeat = False  # If 'true', indicates first time heartbeat polling function is called
        self.firstBeat = 0  # Time of first heartbeat
        self.nextBeat = 0  # Time in the future of next heartbeat
        self.lastBeat = 0  # Time in the past that the last heartbeat occurred
        self.queue = Queue(maxsize=RAMControl.QUEUE_SIZE)  # Use a queue for messages
        self.experimentCallback = None  # Callback into the experiment
        self.abortCallback = None  # Callback into experiment if Control PC dies
        self.isSynced = False  # Indicates that clock syncronization to Control PC has not occurred
        self.ramControlStarted = False  # Indicates that "Start" has not yet been hit on Control PC
        self.config = None  # Use the experiment's config file for RAMControl configuration
        self.clock = None  # Experiment clock

    @classmethod
    def get_instance(cls):
        """Returns a reference to the singleton instance to this class"""
        if RAMControl.singleton_instance is None:
            RAMControl.singleton_instance = RAMControl()
        return RAMControl.singleton_instance

    @staticmethod
    def get_system_time_in_micros():
        """Convenience method to return the system time."""
        return time() * 1000000

    @staticmethod
    def get_system_time_in_millis():
        """Convenience method to return the system time."""
        return int(round(time() * 1000.0))

    def initialize(self, config=None, host=None, port=0):
        """Setup a server connection"""
        # Create a network object
        self.network = Network()

        # Use config information from the experiment.
        # (These should all be in the RAMControl section)
        self.config = config

        # Create a connection and set it to listen for a client to connect.  The 'alternate' host and port below
        # are active during testing when the connection is from and to a single host.
        rtc = self.network.open(host, port)
        if rtc != 0:
            isAlternate = False
            if not config['is_hardwire']:
                alternates = self.network.getAlternateInterfaces()
                for interface in alternates:
                    alternateHost = interface[4][0]
                    alternatePort = interface[4][1]
                    rtc = self.network.open(alternateHost, alternatePort)
                    if rtc == 0:
                        isAlternate = True
                        break
            if not isAlternate:
                return -1

        # Setup a thread to wait for the connection.
        rtc = self.network.waitForConnection()
        if rtc != 0:
            return -2

        return 0

    def connect(self, callback=None, seconds=1):
        """
        Allow for both poll and callback.  The first parameter of the callback is True if the connection
        was successful, and False otherwise.  If 'seconds' is zero and no callback exists, poll once and return.
        Otherwise, use 'seconds' as the polling interval and block until a connection is made, issuing the callback
        each time the poll is made.
        Returns Success(0) if a connection is available, -1 if a connection is not available.
        """
        while True:
            if self.network.isConnected():
                self.network.registerMessageCallback(self.receive_message)
                if callback is not None:
                    callback(True)
                sleep(1)  # Give ControlPC some time to know that we have connected
                return 0
            else:
                if seconds == 0 and callback is None:
                    return -1
                else:
                    sleep(seconds)
                    if callback is not None:
                        callback(False)

    def wait_for_ram_control_started(self, waitingCallback=None, seconds=1):
        """
        Similar to 'connect'. Waits for a message to be recieved. The first parameter of the callback is True
        if the message has been received, and False otherwise. If 'seconds' is zero and no callback exists, poll once
        and return. Otherwise, use 'seconds' as the polling interval and block until a connection is made, issuing
        the callback each time the poll is made.
        Returns 0 if the message was received, -1 if a connection was not received, and -2 if no connection was available
        """
        while True:
            if self.network.isConnected():
                if self.ramControlStarted:
                    if waitingCallback is not None:
                        waitingCallback(True)
                    return 0
                else:
                    if waitingCallback is not None:
                        waitingCallback(False)
                    elif seconds == 0:
                        return -1
                    sleep(seconds)
            else:
                return -2

    def receive_message(self, message):
        """
        A callback that receives messages from the Control PC. Since this method is inside the poll callback, put
        the message in a queue for further processing by the experiment.
        """
        self.queue.put(message, False)  # False indicates to throw an exception if the queue is full

    def get_message(self):
        """
        Returns a message if available, or None if not
        """
        if self.queue.empty():
            return None
        return self.queue.get_nowait()

    @staticmethod
    def split_messages(msg):
        """
        If a message consists of multiple json strings, split it into a list of each of the strings
        """
        return ['%s%s' % ('{' if i > 0 else '', msgPart)
                for (i, msgPart) in
                enumerate(RAMControl.JSON_SPLITTER.split(msg))]

    def process_message(self, msg):
        """
        Process a message from the Control PC
        Currently there are only a couple of messages sent by the Control PC.
        """
        if msg is None:
            return

        # The network buffer can contain multiple messages, so crack each one
        # apart, and process each separately
        logger.info('msg=%s', msg)
        split_msgs = self.split_messages(msg)

        for message in split_msgs:
            json_message = json.loads(message)
            # json_message = str(json_message)
            logger.info('JSON MSG TYPE = %s', json_message['type'])

            if 'type' not in json_message:
                logger.error('JSON received without "TYPE"')
                continue

            mtype = json_message["type"]

            if mtype == "ID":
                pass
            elif mtype == "SYNC":
                # Sync received from Control PC.
                # Echo SYNC back to Control PC with high precision time so
                # that clocks can be aligned.
                if 'num' in json_message.keys():
                    self.send_event(RAMControl.get_system_time_in_millis(),
                                    'SYNC',
                                    RAMControl.get_system_time_in_micros(),
                                    aux_data=json_message['num'])
                else:
                    self.send_event(RAMControl.get_system_time_in_millis(),
                                    'SYNC',
                                    RAMControl.get_system_time_in_micros())
            elif mtype == "SYNCED":
                self.isSynced = True
            elif mtype == "EXIT":
                logger.info("Control PC exit")
                self.disconnect()
                if self.isHeartbeat and self.abortCallback:
                    self.disconnect()
                    self.abortCallback()
            elif mtype == "MESSAGE":
                # Control PC has started receiving messages
                # print(json_message)
                if json_message['data'] == 'STARTED':
                    self.ramControlStarted = True
            else:
                logger.error("Invalid message type: %s", mtype)

    def poll_for_message(self):
        """ Poll and process each message """
        self.process_message(self.get_message())

    def send_message(self, message):
        """
        This blocks until the message is sent.  Returns the total number of characters sent to control PC
        """
        self.network.send(str(12).zfill(
            4))  # in the future this could be used to transmit command id
        self.network.send(str(len(message)).zfill(4))  # length of the message

        ret_val = self.network.send(message)
        print 'SENDING MESSAGE=', message
        return ret_val

        # return self.network.send(message)

    def send_event(self, system_time, event_type, event_data=None,
                   aux_data=None):
        """Format the message

        TODO: Change to JSONRPC and add checksum

        """
        message = self.build_message(system_time, event_type, event_data,
                                     aux_data)
        return self.send_message(message)

    @staticmethod
    def build_message(system_time, event_type, event_data=None, aux_data=None):
        """Build and return a message to be sent to control PC.

        Messages are JSON encoded and are of the following form::

            {
              "time": <laptop timestamp in ms>,
              "type": "name of event type",
              "data": <optional, data associated with event>,
              "aux": <optional, auxiliary data associated with event>
            }

        """
        message = {'time': system_time, 'type': event_type}
        if event_data:
            message.update({'data': event_data})

        if aux_data:
            message.update({'aux': aux_data})

        return json.dumps(message)

    def ready_control_pc(self, clock, callbacks, config, subject, sessionNum):
        """
        Setup the connection to the Control PC and do various housekeeping tasks.
        - Send name of this experiment
        - Send subject id
        - Send version number
        - Send session information
        - Ready two polling tasks, to read messages from the network, and to process events based on those messages
        - Do a sequence of SYNC and SYNCED messages so that the Control PC knows the offset in time between the
          system clock on this computer, and the system clock on the Control PC.
        - Start generating heartbeat messages so that the Control PC knows if we die or are interrupted.
        - Wait to return until "START" is pressed on the control PC
        Return 0 (Success), <0 (Various Errors)
        """
        self.initialize(config)
        self.clock = clock
        self.abortCallback = callbacks.abort_callback
        if self.connect(callbacks.connect_callback) == 0:
            self.send_event(RAMControl.get_system_time_in_millis(), 'EXPNAME',
                            config['EXPERIMENT_NAME'])
            self.send_event(RAMControl.get_system_time_in_millis(), 'VERSION',
                            config['VERSION_NUM'])
            self.send_event(RAMControl.get_system_time_in_millis(), 'SESSION',
                            {'session_number': sessionNum,
                            'session_type': config['STIM_TYPE']})
            self.send_event(RAMControl.get_system_time_in_millis(), 'SUBJECTID',
                            subject)
            self.start_network_poll()  # Ready to receive message from the control PC
            self.start_message_poll()  # Ready to process message from the control PC
            if self.align_clocks(callbacks.sync_callback):  # Align clocks
                return -1
            self.start_heartbeat_poll(callbacks.abort_callback,
                                      config['heartbeat'])
            ramControlStarted = self.wait_for_ram_control_started(
                callbacks.wait_for_start_callback)
            if ramControlStarted < 0:
                return -3
            return 0
        return -2

    @staticmethod
    def decode_message(message):
        """
        Decode a message and return tuple of its parts.
        """
        separators = '\\' + RAMControl.MSG_START + '|\\' + RAMControl.MSG_SEPARATOR + '|\\' + RAMControl.MSG_END
        token = re.split(separators, message)
        n = len(token)
        if (n < 4 or n > 6) or (message[0] != RAMControl.MSG_START or message[
            -1] != RAMControl.MSG_END):
            return -1, 0, '', ''
        if not token[1].isdigit():
            return -2, 0, '', ''
        t0 = int(token[1])
        id = token[2]
        data = ''
        aux = ''
        if n >= 5:
            data = token[3]
            if n == 6:
                aux = token[4]
        return t0, id, data, aux

    def disconnect(self):
        """
        Disconnect and close the connection to the Control PC.
        """
        if (self.network):
            self.network.stopWaitForData()
            sleep(0.5)  # Wait for threads to exit before closing connection
            self.network.close()

    def send_heartbeat_polled(self, interval_millis):
        """Send continuous heartbeat events every ``interval_millis``. The
        computation assures that the average interval between heartbeats will be
        interval_millis rather than interval_millis + some amount of
        computational overhead because it is relative to a fixed t0.

        """
        if self.isHeartbeat:
            t1 = RAMControl.get_system_time_in_millis()
            if (t1 - self.firstBeat) > self.nextBeat:
                self.nextBeat = self.nextBeat + interval_millis
                self.lastBeat = t1
                self.send_event(self.lastBeat, 'HEARTBEAT', interval_millis)
        else:  # First time
            self.isHeartbeat = True
            self.firstBeat = self.lastBeat = RAMControl.get_system_time_in_millis()
            self.nextBeat = interval_millis
            self.send_event(self.lastBeat, 'HEARTBEAT', interval_millis)

    def start_heartbeat_poll(self, abortCallback, intervalMillis):
        """
        Start polled version of heartbeat by adding a poll callback function
        """
        self.isHeartbeat = False  # Needs to be reset before starting the heartbeat
        self.abortCallback = abortCallback
        addPollCallback(self.send_heartbeat_polled, intervalMillis)

    def stop_heartbeat_poll(self):
        """
        Stop polled version of heartbeat by removing the poll callback function
        """
        if self.isHeartbeat:
            removePollCallback(self.send_heartbeat_polled)
            self.isHeartbeat = False
            self.abortCallback = None

    def network_poll(self):
        """
        Called by hardware loop.  Should be as short and efficient as possible!
        """
        rtc = self.network.poll()
        if rtc >= 0:
            return
        self.stop_network_poll()
        print 'Error from receive - stopping Poll'
        if self.abortCallback:
            self.abortCallback()

    def start_network_poll(self):
        """
        Install a network handler into the hardware polling loop
        """
        addPollCallback(self.network_poll)

    def stop_network_poll(self):
        """
        Remove a network handler from the hardware polling loop
        """
        removePollCallback(self.network_poll)

    def start_message_poll(self):
        """
        Install a message received handler into the hardware polling loop
        """
        addPollCallback(self.poll_for_message)

    def stop_message_poll(self):
        """
        Remove a message received handler from the hardware polling loop
        """
        removePollCallback(self.poll_for_message)

    def align_clocks(self, callback, clock=None):
        """
        Task computer starts the process by sending "ALIGNCLOCK' request.
        Control PC will send a sequence of SYNC messages which are echoed back to it
        When it is complete, the Control PC will send a SYNCED message, which indicates
        it has completed the clock alignment and it is safe for task computer to proceed
        to the next step.
        """
        self.isSynced = False
        self.send_event(RAMControl.get_system_time_in_millis(), 'ALIGNCLOCK')
        print "Requesting ALIGNCLOCK"
        for i in range(120):  # 60 seconds (normally takes < 6 seconds)
            if callback:
                callback(self.isSynced, i)
            if self.isSynced:
                print 'Sync Complete'
                break
            else:
                # Try to pause using the pyepl clock if possible, so poll can still run
                if clock:
                    clock.delay(500)
                    clock.wait()
                else:
                    sleep(0.5)
        return 0 if self.isSynced else -1

    def sync_callback(self, millis):
        """
        THIS METHOD IS ONLY USED FOR DETERMINING LATENCY.  IT IS NOT CALLED IN THE PRODUCTION SYSTEM
        This method gets called immediately after a sync pulse has been sent.  Logic below simultaneously
        sends a SYNC message to the Control PC, thus enabling the Control PC to align clocks.  This continues
        until a message is received from the Control PC which asynchronously sets 'isSynced', which is sent
        back via a callback to the experiment.
        """
        self.send_event(RAMControl.get_system_time_in_millis(), 'SYNC')
        if self.experimentCallback:
            self.experimentCallback(self.isSynced)

    def send_sync_message_to_control_pc(self):
        """
        THIS METHOD IS ONLY USED FOR DETERMINING LATENCY.  IT IS NOT CALLED IN THE PRODUCTION SYSTEM
        Do not do anything below that will take more than the inter-sync message interval config.syncInterval,
        including displaying messages on the screen unless the config.syncInterval is at least one second.
        For example, flashStimulus() will use about 800 ms, so do not call this function in the exerperimentCallback()
        unless config.syncInterval >= 1000.
        """
        if self.experimentCallback:
            self.experimentCallback(
                False)  # False indicates that sync operation is not yet complete
        self.send_event(RAMControl.get_system_time_in_millis(), 'SYNC')

    def measure_sync(self, pulses, interval, eeg, clock):
        """
        THIS METHOD IS ONLY USED FOR DETERMINING LATENCY.  IT IS NOT CALLED IN THE PRODUCTION SYSTEM
        Code used to measure latency between control PC receipt of syncbox pulses and 'SYNC' events sent
        via the internet.  This method is not called in a production setting.
        """
        missed = 0
        for _ in range(pulses):
            t = RAMControl.get_system_time_in_millis()
            eeg.timedPulse(10, pulsePrefix='SYNC_',
                           callback=self.send_sync_message_to_control_pc)
            delta = interval - (RAMControl.get_system_time_in_millis() - t)
            if delta > 0:
                sleep(
                    delta / 1000.0)  # TODO: Replace by self.clock.delay so pollEvent is called
            else:
                missed += 1
        if self.experimentCallback:
            self.experimentCallback(
                True)  # True indicates that sync operation is complete
        return missed

    def time_sync(self, eeg, clock, syncCount, syncInterval,
                  experimentCallback=None):
        """
        THIS METHOD IS ONLY USED FOR DETERMINING LATENCY.  IT IS NOT CALLED IN THE PRODUCTION SYSTEM
        Create a sequence of sync pulses
        """
        self.isSynced = False
        self.clock = clock
        self.experimentCallback = experimentCallback
        sleep(2)  # Give Control PC time to get ready
        if self.config['syncMeasure']:
            self.measure_sync(syncCount, syncInterval, eeg, clock)
        for _ in range(
                        600 * 15):  # Already connected.  Allow some time to sync, then give up TODO: 15 mins
            self.poll_for_message()
            sleep(0.1)
            if self.isSynced:
                break
        return self.isSynced


class RAMCallbacks(object):
    PRINT_STATUSES = True

    def __init__(self, config, clock, video):
        self.config = config
        self.clock = clock
        self.video = video

    def connect_callback(self, is_connected):
        """
        Callled when task laptop is synchronizing to control PC for first time
        :param is_connected: whether control PC has connected
        """
        if is_connected:
            if self.PRINT_STATUSES:
                print 'Connected to Control PC'
            RAMControl.get_instance().send_event(
                RAMControl.get_system_time_in_millis(), 'DEFINE',
                self.config.sys2['state_list'])
        else:
            flashStimulus(
                Text('Searching for Control PC', size=self.config.wordHeight),
                800,
                clk=self.clock)
            if self.PRINT_STATUSES:
                print 'Connecting...'

    def sync_callback(self, is_synced, count):
        """
        Called when waiting for Control PC to connect
        :param is_synced: True once control PC has connected
        :param count: how many attempts have been made
        """
        if is_synced and self.PRINT_STATUSES:
            print 'Connected to Control PC'
        else:
            flashStimulus(
                Text('Connecting to Control PC', size=self.config.wordHeight),
                1000,
                clk=self.clock)

    def abort_callback(self):
        """
        Called when heartbeats encounter a network error
        """
        self.video.clear('black')
        self.video.showCentered(
            Text('Control PC not responding\nSession ending\n in 15 seconds',
                 size=.05))
        self.video.updateScreen(self.clock)
        self.clock.delay(5000)
        self.clock.wait()
        control = RAMControl.get_instance()
        control.stop_heartbeat_poll()
        control.disconnect()
        sys.exit(0)

    def wait_for_start_callback(self, is_started):
        """
        Called when waiting for start to be pressed on Control PC
        Called once when Control PC has connected
        :param is_started: True once Control PC connects
        """
        if not is_started:
            flashStimulus(Text('Press START on control PC\n to begin',
                               size=self.config.wordHeight),
                          1000,
                          clk=self.clock)
        else:
            flashStimulus(
                Text('Control PC Started', size=self.config.wordHeight),
                1000,
                clk=self.clock)

    def resync_callback(self, is_synced, sync_attempts):
        """
        Called when resynchronizing to the control PC between lists
        :param is_synced: True once synchronization is complete
        :param sync_attempts: Number of attempts to synchronize that have been made
        """
        loc = [.8, .05]
        if is_synced:
            text_to_show = Text('Synchronized', size=.02)
        else:
            text_to_show = Text('Re-synchronizing' + '.' * (sync_attempts % 4),
                                size=.02)
        self.video.clear('black')
        self.video.showAnchored(text_to_show, NORTHWEST,
                                self.video.propToPixel(*loc))
        self.video.updateScreen()
