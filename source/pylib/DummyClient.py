from Network import Network
from time import time, sleep
from pyepl.locals import Experiment
from pyepl.hardware import addPollCallback, removePollCallback
from pyepl.hardware.timing import pollEvents

TO_CONNECTION = '192.168.137.1'
# TO_CONNECTION = '192.168.0.113'
FROM_CONNECTION = '192.168.137.200'
PORT = 8888
ECHO = 1
SHOW = 0
ALIGN = 0
SERVER = 1
MESSAGES = 5000

class DummyClient:
    """
    Simple client that echos any messages received from the server.  This code can be used in lieu of
    a Control PC to check some very basic networking and handshake logic.
    THIS CODE IS NOT PART OF THE PRODUCTION SYSTEM, BUT IS USEFUL FOR TESTING
    """
    def __init__(self):
        self.controlPC = Network()
        self.messageCount = 0;

    def controlPCReceivedMessage(self, message):
        self.lastMessageReceived = message
        self.messageCount = self.messageCount + 1;
        if SHOW:
            print 'RECV ControlPC: ' + message
        if ECHO:
            self.controlPC.send('ECHO: ' + message)

    def connect(self):
        # This simulates a connection from the Control PC
        rtc = self.controlPC.connect(FROM_CONNECTION, TO_CONNECTION)
        if rtc != 0:
            print "Problem opening connection"
            return
        sleep(0.5) # Wait for server to connect
        self.controlPC.registerMessageCallback(self.controlPCReceivedMessage)
        if ALIGN:
            self.alignClocks();

    def pollNetwork(self):
        rtc = self.controlPC.poll()
        if rtc >= 0:
            return
        self.removePollCallback(self.pollNetwork)
        print 'Error from receive - stopping Poll'

    def server(self):
        rtc = self.controlPC.open(FROM_CONNECTION, PORT)
        if rtc != 0:
            print "Problem setting up server"
            return;
        rtc = self.controlPC.listen()
        if rtc != 0:
            print "Problem with listen()"
            return;
        self.controlPC.registerMessageCallback(self.controlPCReceivedMessage)
        addPollCallback(self.pollNetwork)

    def alignClocks(self):
        # Wait for the first couple of messages to come through
        self.messageCount = 0;
        while 0 == self.controlPC.poll():
            sleep(0.1)

        # Send sync messages
        for x in range(5):
            self.controlPC.send('[%020.0f~0~SYNC]' % round(time() * 1000))
            while 0 == self.controlPC.poll(): # Wait for receipt of a message
                sleep(0.1)
        sleep(0.1)
        self.controlPC.send('[%020.0f~0~SYNCED]' % round(time() * 1000))

    def cleanupControlPC(self):
        if self.controlPC != None:
            self.controlPC.stopWaitForData()
            sleep(0.1) # Time for thread to stop

if __name__ == '__main__':
    exp = Experiment() # Start Pyepl so that pollEvents works
    client = DummyClient()
    if SERVER:
        client.server()
    else:
        client.connect()
    while True:
        pollEvents();
    if SERVER:
        client.controlPC.stopNetworkPoll()
    client.cleanupControlPC()
