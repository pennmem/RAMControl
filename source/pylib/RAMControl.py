"""
Interfaces to the Control PC
"""
from Network import Network
import re
from Queue import Queue
from time import time, sleep
from pyepl.hardware import addPollCallback, removePollCallback
import select
import json
from pyepl.locals import *


class RAMControl:
    JSON_SPLITTER = re.compile(
        '(?<=})\s*{')  # REGEXP to split consecutive JSON message
    # NOTE: Removes leading brace of all but the first message

    QUEUE_SIZE = 20  # Blocks if the queue is full

    # Use getInstance() to instantiate this class
    singletonInstance = None

    def __init__(self):
        """ Constructor  - Do not call instantiate RAMControl directly, but use getInstance instead """
        self.network = None  # Network class instance
        self.isHeartbeat = False  # If 'true', indicates first time heartbeat polling function is called
        self.firstBeat = 0  # Time of first heartbeat
        self.nextBeat = 0  # Time in the future of next heartbeat
        self.lastBeat = 0  # Time in the past that the last heartbeat occurred
        self.queue = Queue(
            maxsize=RAMControl.QUEUE_SIZE)  # Use a queue for messages
        self.experimentCallback = None  # Callback into the experiment
        self.abortCallback = None  # Callback into experiment if Control PC dies
        self.isSynced = False  # Indicates that clock syncronization to Control PC has not occurred
        self.ramControlStarted = False  # Indicates that "Start" has not yet been hit on Control PC
        self.config = None  # Use the experiment's config file for RAMControl configuration
        self.clock = None  # Experiment clock
        self.sdRef = None  # Bonjour handle

    def getInstance(cls):
        """
        Returns a reference to the singleton instance to this class
        """
        if (RAMControl.singletonInstance == None):
            RAMControl.singletonInstance = RAMControl()
        return RAMControl.singletonInstance

    # Force getInstance() to be a class method
    getInstance = classmethod(getInstance)

    def getSystemTimeInMicros(cls):
        """
        Convenience method to return the system time.
        """
        return time() * 1000000

    getSystemTimeInMicros = classmethod(getSystemTimeInMicros)

    def getSystemTimeInMillis(cls):
        """
        Convenience method to return the system time.
        """
        # return int(round(RAMControl.getSystemTimeInMicros() / 1000.0))
        return int(round(time() * 1000.0))

    getSystemTimeInMillis = classmethod(getSystemTimeInMillis)

    def initialize(self, config=None, host=None, port=0):
        """
        Setup a server connection
        """
        # Create a network object
        self.network = Network()

        # Use config information from the experiment.  (These should all be in the RAMControl section)
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

        # Advertise a connection to me via Bonjour
        if not config['is_hardwire']:
            self.startBonjour(self.network.toHost, self.network.port)

        # Setup a thread to wait for the connection.
        rtc = self.network.waitForConnection()
        if rtc != 0:
            return -2

        return 0

    def connect(self, connectedCallback=None, seconds=1):
        """
        Allow for both poll and callback.  The first parameter of the callback is True if the connection
        was successful, and False otherwise.  If 'seconds' is zero and no callback exists, poll once and return.
        Otherwise, use 'seconds' as the polling interval and block until a connection is made, issuing the callback
        each time the poll is made.
        Returns Success(0) if a connection is available, -1 if a connection is not available.
        """
        while True:
            if self.network.isConnected():
                self.network.registerMessageCallback(self.receiveMessage)
                if connectedCallback != None:
                    connectedCallback(True)
                sleep(
                    1)  # Give ControlPC some time to know that we have connected
                return 0
            else:
                if seconds == 0 and connectedCallback == None:
                    return -1
                else:
                    sleep(seconds)
                    if connectedCallback != None:
                        connectedCallback(False)

    def waitForRamControlStarted(self, waitingCallback=None, seconds=1):
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
                    if waitingCallback != None:
                        waitingCallback(True)
                    return 0
                else:
                    if waitingCallback != None:
                        waitingCallback(False)
                    elif seconds == 0:
                        return -1
                    sleep(seconds)
            else:
                return -2

    # def receiveMessage(self, message):
    #     """
    #     A callback that receives messages from the Control PC. Since this method is inside the poll callback, put
    #     the message in a queue for further processing by the experiment.
    #     """
    #     self.queue.put(message, False) # False indicates to throw an exception if the queue is full
    #     #print message # TODO: Remove this

    def receiveMessage(self, message):
        """
        A callback that receives messages from the Control PC. Since this method is inside the poll callback, put
        the message in a queue for further processing by the experiment.
        """
        self.queue.put(message,
                       False)  # False indicates to throw an exception if the queue is full
        # print message # TODO: Remove this

    def getMessage(self):
        """
        Returns a message if available, or None if not
        """
        if self.queue.empty():
            return None
        return self.queue.get_nowait()

    @staticmethod
    def splitMessages(msg):
        """
        If a message consists of multiple json strings, split it into a list of each of the strings
        """
        return ['%s%s' % ('{' if i > 0 else '', msgPart)
                for (i, msgPart) in
                enumerate(RAMControl.JSON_SPLITTER.split(msg))]

    def processMessage(self, msg):
        """
        Process a message from the Control PC
        Currently there are only a couple of messages sent by the Control PC.
        """
        if msg == None:
            return

        # The network buffer can contain multiple messages, so crack each one apart, and process each separately
        print 'msg=', msg
        split_msgs = self.splitMessages(msg)
        print 'split_msgs=', split_msgs
        # for message in self.splitMessages(msg):
        for message in split_msgs:
            json_message = json.loads(message)
            # json_message = str(json_message)
            print 'json_message=', json_message
            print 'JSON MSG TYPE = ', json_message['type']

            if 'type' not in json_message:
                print 'JSON received without "TYPE"'
                continue
            for case in switch(json_message['type']):
                print 'case=', case
                if case('ID'):
                    break
                if case('SYNC'):
                    # Sync received from Control PC.
                    # Echo SYNC back to Control PC with high precision time so that clocks can be aligned.
                    if 'num' in json_message.keys():
                        # orig
                        # self.sendEvent(RAMControl.getSystemTimeInMillis(), 'SYNC', RAMControl.getSystemTimeInMicros())
                        self.sendEvent(RAMControl.getSystemTimeInMillis(),
                                       'SYNC',
                                       RAMControl.getSystemTimeInMicros(),
                                       aux_data=json_message['num'])
                    else:
                        self.sendEvent(RAMControl.getSystemTimeInMillis(),
                                       'SYNC',
                                       RAMControl.getSystemTimeInMicros())
                    break
                if case('SYNCED'):
                    # Control PC is done clock alignment
                    self.isSynced = True
                    break
                if case('EXIT'):
                    # Control PC is exiting.  If heartbeat is active, this is a premature abort.
                    print "Control PC exit"
                    self.disconnect()
                    if self.isHeartbeat and self.abortCallback:
                        self.disconnect()
                        self.abortCallback()
                if case('MESSAGE'):
                    # Control PC has started receiving messages
                    # print(json_message)
                    if json_message['data'] == 'STARTED':
                        self.ramControlStarted = True
                    break

                if case():
                    print 'Invalid ID returned from Control PC'
                    break

    def pollForMessage(self):
        """ Poll and process each message """
        self.processMessage(self.getMessage())

    # def sendMessage(self, message):
    #     """
    #     This blocks until the message is sent.  Returns the total number of characters sent to control PC
    #     """
    #     #print 'sending', message
    #     return self.network.send(message)

    def sendMessage(self, message):
        """
        This blocks until the message is sent.  Returns the total number of characters sent to control PC
        """
        # print 'sending', message
        import time
        # time.sleep(0.1)
        self.network.send(str(12).zfill(
            4))  # in the future this could be used to transmit command id
        self.network.send(str(len(message)).zfill(4))  # length of the message

        ret_val = self.network.send(message)
        print 'SENDING MESSAGE=', message
        return ret_val

        # return self.network.send(message)

    def sendEvent(self, system_time, event_type, event_data=None,
                  aux_data=None):
        """Format the message

        TODO: Change to JSONRPC and add checksum

        """
        message = self.buildMessage(system_time, event_type, event_data,
                                    aux_data)
        return self.sendMessage(message)

    @staticmethod
    def buildMessage(system_time, event_type, event_data=None, aux_data=None):
        """Build and return a message to be sent to control PC.

        Messages are JSON encoded and are of the following form::

            {
              "time": <laptop timestamp in ms>,
              "type": "name of event type",
              "data": <optional, data associated with event>,
              "aux_data": <optional, auxiliary data associated with event>
            }

        """
        message = {'time': system_time, 'type': event_type}
        if event_data:
            message.update({'data': event_data})

        if aux_data:
            message.update({'aux': aux_data})

        return json.dumps(message)

    def readyControlPC(self, clock, callbacks, config, subject, sessionNum):
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
            self.sendEvent(RAMControl.getSystemTimeInMillis(), 'EXPNAME',
                           config['EXPERIMENT_NAME'])
            self.sendEvent(RAMControl.getSystemTimeInMillis(), 'VERSION',
                           config['VERSION_NUM'])
            self.sendEvent(RAMControl.getSystemTimeInMillis(), 'SESSION',
                           {'session_number': sessionNum,
                            'session_type': config['STIM_TYPE']})
            self.sendEvent(RAMControl.getSystemTimeInMillis(), 'SUBJECTID',
                           subject)
            self.startNetworkPoll()  # Ready to receive message from the control PC
            self.startMessagePoll()  # Ready to process message from the control PC
            if self.alignClocks(callbacks.sync_callback):  # Align clocks
                return -1
            self.startHeartbeatPoll(callbacks.abort_callback,
                                    config['heartbeat'])
            ramControlStarted = self.waitForRamControlStarted(
                callbacks.wait_for_start_callback)
            if ramControlStarted < 0:
                return -3
            return 0
        return -2

    def decodeMessage(self, message):
        """
        Decode a message and return tuple of its parts.
        """
        separators = '\\' + RAMControl.MSG_START + '|\\' + RAMControl.MSG_SEPARATOR + '|\\' + RAMControl.MSG_END
        token = re.split(separators, message)
        n = len(token)
        if (n < 4 or n > 6) or (message[0] != RAMControl.MSG_START or message[
            -1] != RAMControl.MSG_END):
            return (-1, 0, '', '')
        if not token[1].isdigit():
            return (-2, 0, '', '')
        t0 = int(token[1])
        id = token[2]
        data = ''
        aux = ''
        if n >= 5:
            data = token[3]
            if n == 6:
                aux = token[4]
        return (t0, id, data, aux)

    def disconnect(self):
        """
        Disconnect and close the connection to the Control PC.
        """
        if (self.network):
            self.network.stopWaitForData()
            sleep(0.5)  # Wait for threads to exit before closing connection
            self.network.close()

    def sendHeartbeatPolled(self, interval_millis):
        """Send continuous heartbeat events every ``interval_millis``. The
        computation assures that the average interval between heartbeats will be
        interval_millis rather than interval_millis + some amount of
        computational overhead because it is relative to a fixed t0.

        """
        if self.isHeartbeat:
            t1 = RAMControl.getSystemTimeInMillis()
            if (t1 - self.firstBeat) > self.nextBeat:
                self.nextBeat = self.nextBeat + interval_millis
                self.lastBeat = t1
                self.sendEvent(self.lastBeat, 'HEARTBEAT', interval_millis)
        else:  # First time
            self.isHeartbeat = True
            self.firstBeat = self.lastBeat = RAMControl.getSystemTimeInMillis()
            self.nextBeat = interval_millis
            self.sendEvent(self.lastBeat, 'HEARTBEAT', interval_millis)

    def startHeartbeatPoll(self, abortCallback, intervalMillis):
        """
        Start polled version of heartbeat by adding a poll callback function
        """
        self.isHeartbeat = False  # Needs to be reset before starting the heartbeat
        self.abortCallback = abortCallback
        addPollCallback(self.sendHeartbeatPolled, intervalMillis)

    def stopHeartbeatPoll(self):
        """
        Stop polled version of heartbeat by removing the poll callback function
        """
        if self.isHeartbeat:
            removePollCallback(self.sendHeartbeatPolled)
            self.isHeartbeat = False
            self.abortCallback = None

    def networkPoll(self):
        """
        Called by hardware loop.  Should be as short and efficient as possible!
        """
        rtc = self.network.poll()
        if rtc >= 0:
            return
        self.stopNetworkPoll()
        print 'Error from receive - stopping Poll'
        if self.abortCallback:
            self.abortCallback()

    def startNetworkPoll(self):
        """
        Install a network handler into the hardware polling loop
        """
        addPollCallback(self.networkPoll)

    def stopNetworkPoll(self):
        """
        Remove a network handler from the hardware polling loop
        """
        removePollCallback(self.networkPoll)

    def startMessagePoll(self):
        """
        Install a message received handler into the hardware polling loop
        """
        addPollCallback(self.pollForMessage)

    def stopMessagePoll(self):
        """
        Remove a message received handler from the hardware polling loop
        """
        removePollCallback(self.pollForMessage)

    def alignClocks(self, experimentCallback, clock=None):
        """
        Task computer starts the process by sending "ALIGNCLOCK' request.
        Control PC will send a sequence of SYNC messages which are echoed back to it
        When it is complete, the Control PC will send a SYNCED message, which indicates
        it has completed the clock alignment and it is safe for task computer to proceed
        to the next step.
        """
        self.isSynced = False
        self.sendEvent(RAMControl.getSystemTimeInMillis(), 'ALIGNCLOCK')
        print "Requesting ALIGNCLOCK"
        for i in range(120):  # 60 seconds (normally takes < 6 seconds)
            if experimentCallback:
                experimentCallback(self.isSynced, i)
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

    def syncCallback(self, millis):
        """
        THIS METHOD IS ONLY USED FOR DETERMINING LATENCY.  IT IS NOT CALLED IN THE PRODUCTION SYSTEM
        This method gets called immediately after a sync pulse has been sent.  Logic below simultaneously
        sends a SYNC message to the Control PC, thus enabling the Control PC to align clocks.  This continues
        until a message is received from the Control PC which asynchronously sets 'isSynced', which is sent
        back via a callback to the experiment.
        """
        self.sendEvent(RAMControl.getSystemTimeInMillis(), 'SYNC')
        if self.experimentCallback:
            self.experimentCallback(self.isSynced)

    def sendSyncMessageToControlPC(self):
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
        self.sendEvent(RAMControl.getSystemTimeInMillis(), 'SYNC')

    def measureSync(self, pulses, interval, eeg, clock):
        """
        THIS METHOD IS ONLY USED FOR DETERMINING LATENCY.  IT IS NOT CALLED IN THE PRODUCTION SYSTEM
        Code used to measure latency between control PC receipt of syncbox pulses and 'SYNC' events sent
        via the internet.  This method is not called in a production setting.
        """
        missed = 0
        for _ in range(pulses):
            t = RAMControl.getSystemTimeInMillis()
            eeg.timedPulse(10, pulsePrefix='SYNC_',
                           callback=self.sendSyncMessageToControlPC)
            delta = interval - (RAMControl.getSystemTimeInMillis() - t)
            if delta > 0:
                sleep(
                    delta / 1000.0)  # TODO: Replace by self.clock.delay so pollEvent is called
            else:
                missed = missed + 1
        if self.experimentCallback:
            self.experimentCallback(
                True)  # True indicates that sync operation is complete
        return missed

    def timeSync(self, eeg, clock, syncCount, syncInterval,
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
            self.measureSync(syncCount, syncInterval, eeg, clock)
        for _ in range(
                        600 * 15):  # Already connected.  Allow some time to sync, then give up TODO: 15 mins
            self.pollForMessage()
            sleep(0.1)
            if self.isSynced:
                break
        return self.isSynced

    def bonjourCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        """
        Bonjour reports it's status via this callback
        """
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            print 'Registered service:'
            print '  name    =', name
            print '  regtype =', regtype
            print '  domain  =', domain

    def startBonjour(self, host, port):
        """
        Start the Bonjour service indicating that this is a 'RAMTaskComputer' accepting TCP/IP connections on the
        specified port.
        """
        name = 'RAMTaskComputer'
        regtype = '_ip._tcp'

        self.sdRef = pybonjour.DNSServiceRegister(name=name,
                                                  regtype=regtype,
                                                  port=port,
                                                  txtRecord=pybonjour.TXTRecord(
                                                      {'macaddress': host}),
                                                  callBack=self.bonjourCallback)
        try:
            ready = select.select([self.sdRef], [], [])
            if self.sdRef in ready[0]:
                pybonjour.DNSServiceProcessResult(self.sdRef)
        except:
            print "Cannot register Bonjour service"

    def stopBonjour(self):
        """
        Stop advertising that the RAMTaskComputer service is available
        """
        self.sdRef.close()

    def sendStimParameters(self, amplitude=None, pulseFrequency=None,
                           nPulses=None, burstFrequency=None, nBursts=None,
                           pulseDuration=None):
        """
        Wrapper function to send SETSTIMPARAM and MAKESTIMSEQUENCE messages to the control PC
        (Only used for open-loop tasks)
        """
        if amplitude != None:
            self.sendEvent(this.getSystemTimeInMillis(), 'SETSTIMPARAM',
                           'AMPLITUDE', amplitude)

        if pulseFrequency != None:
            self.sendEvent(this.getSystemTimeInMillis(), 'SETSTIMPARAM',
                           'PULSEFREQUENCY', pulseFrequency)

        if nPulses != None:
            self.sendEvent(this.getSystemTimeInMillis(), 'SETSTIMPARAM',
                           'NPULSES', nPulses)

        if burstFrequency != None:
            self.sendEvent(this.getSystemTimeInMillis(), 'SETSTIMPARAM',
                           'BURSTFREQUENCY', burstFrequency)

        if nBursts != None:
            self.sendEvent(this.getSystemTimeInMillis(), 'SETSTIMPARAM',
                           'NBURSTS', nBursts)

        if pulseDuration != None:
            self.sendEvent(this.getSystemTimeInMillis(), 'SETSTIMPARAM',
                           'PULSEDURATION', pulseDuration)

        return self.sendEvent(this.getSystemTimeInMillis(), 'MAKESTIMSEQUENCE')

    def triggerStimulation(self):
        """
        Wrapper function to send TRIGGERSTIM event to the control PC
        (Only used for open-loop tasks)
        """
        return self.sendEvent(this.getSystemTimeInMillis(), 'TRIGGERSTIM')


# This class provides the functionality we want. You only need to look at
# this if you want to know how this works. It only needs to be defined
# once, no need to muck around with its internals.
class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:  # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


class RAMCallbacks:
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
            RAMControl.getInstance().sendEvent(
                RAMControl.getSystemTimeInMillis(), 'DEFINE',
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
        control = RAMControl.getInstance()
        control.stopHeartbeatPoll()
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
