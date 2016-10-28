import unittest
import inspect
import threading
from time import sleep
from Network import Network
from random import randrange
from threading import Thread
"""
Test Network class
"""
# End-to-end tests require two distinct connections.  I've used the standard wireless adapter + a wireless USB
CONNECTION1 = '165.123.62.36'
CONNECTION2 = '165.123.62.74'
# CONNECTION1 = '192.168.0.60'
# CONNECTION2 = '192.168.0.51'

MESSAGE_COUNT = 20

g_startThreadCount = 0      # It's important to make sure no threads are leaked

class TestNetwork(unittest.TestCase):
    """
    Tests assume dual network interfaces that can talk to each other, for example two wireless interfaces to the same network,
    or a hardwire connection to two ethernet ports with a loopback cable.
    """
    messageCount1 = 0
    messageCount2 = 0
    messageBuffer1 = []
    messageBuffer2 = []
    connection1 = None
    connection2 = None
    msg_s2c = '[Message from server to client]'
    msg_c2s = '[Message from client to server]'
    isPolling = False

    """
    Support methods for the tests
    """

    def createServer(self):
        con1 = Network()
        # Create a connection1 and set it to listen for connection
        rtc = con1.open(CONNECTION1)
        self.assertEqual(rtc, 0)
        self.assertFalse(con1.isConnected())
        self.assertFalse(con1.isListening())
        rtc = con1.waitForConnection() # Server creates thread to wait for connection
        self.assertEqual(rtc, 0)
        sleep(0.1) # Wait for thread to start
        self.assertTrue(con1.isListening())
        self.assertFalse(con1.isConnected())
        return con1

    def createClient(self, con1):
        con2 = Network()
        rtc = con2.connect(CONNECTION2, CONNECTION1)
        self.assertEqual(rtc, 0)
        sleep(1) # Wait for server to connect
        self.assertFalse(con1.isListening()) # Connection#1 is finished listening
        self.assertTrue(con1.isConnected())  # Connection#1 has connected
        return con2

    def receivedMessage1(self, message):
        # Account for receiving multiple messages which happens if the receiver is busy too long.
        msgs = message.split(']')
        for m in msgs:
            if len(m) > 0:
                self.messageCount1 = self.messageCount1 + 1
                message = m + ']'
                self.messageBuffer1.append(message)
                print '1) Received message %d: %s ' % (self.messageCount1, message)

    def receivedMessage2(self, message):
        msgs = message.split(']')
        for m in msgs:
            if len(m) > 0:
                self.messageCount2 = self.messageCount2 + 1
                message = m + ']'
                self.messageBuffer2.append(message)
                print '1) Received message %d: %s ' % (self.messageCount2, message)

    def pingPongMessage1(self, message):
        self.messageCount1 = self.messageCount1 + 1
        self.messageBuffer1.append(message)
        print 'S) Received message %d: %s ' % (self.messageCount1, message)
        if self.messageCount1 <= MESSAGE_COUNT: # One more send here than below
            self.connection1.send(self.msg_s2c)

    def pingPongMessage2(self, message):
        self.messageCount2 = self.messageCount2 + 1
        self.messageBuffer2.append(message)
        print 'C) Received message %d: %s ' % (self.messageCount1, message)
        if self.messageCount2 < MESSAGE_COUNT:
            self.connection2.send(self.msg_c2s)

    def flipFlopPoller(self, con1, con2):
        self.isPolling = True
        while self.isPolling:
            x = randrange(2)
            if 0 == x:
                con1.poll()
            else:
                con2.poll()

    """
    The following are the tests
    """
    def test0_DoFirst(self):
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        g_startThreadCount = threading.active_count() # Save starting thread count to detect leaks later
        self.assertTrue(True)

    def test1_OpenClose(self):
        """
        Test basic functioning on localhost
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        connection = Network()
        rtc = connection.open('localhost');
        self.assertEqual(rtc, 0)
        connection.close()
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test2_CreateConnection(self):
        """
        Test if connection between client and server can be established
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con2 = self.createClient(con1) # Connection from client to con1
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test3_MultipleConnectAndDisconnects(self):
        """
        This test was useful to trap CLOSE_WAIT conditions and 'Address in use' conditions that prevent a IP:PORT from
        being re-opened after it was previously closed
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        for n in range(0, 3):
            con1 = self.createServer()
            con2 = self.createClient(con1)
            # That's all for now
            con2.close()
            con1.close()
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test4_TransferDataFromClientToServerThreaded(self):
        """
        Send some data from the client to the server.  This is actually less useful in our case, since most transfers
        go the other way.  However it's possible that this will be needed in the future, so verify it works.
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con2 = self.createClient(con1) # Connection from client to con1
        con1.startMessageThreadWithCallback(self.receivedMessage1)
        sleep(0.1) # Time for thread start
        self.assertTrue(con1.isWaitingForData)
        self.messageCount = 0
        con2.send(self.msg_c2s)
        sleep(0.5)
        con1.stopWaitForData()
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertTrue(self.messageCount1 > 0)
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test5_TransferDataFromClientToServerPolled(self):
        """
        Send some data from the client to the server.  This is actually less useful in our case, since most transfers
        go the other way.  However it's possible that this will be needed in the future, so verify it works.
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con1.registerMessageCallback(self.receivedMessage1)
        con2 = self.createClient(con1) # Connection from client to con1
        self.messageCount1 = 0
        self.assertTrue(con1.poll() == 0) # No data yet
        con2.send(self.msg_c2s)
        isData = False
        for i in range(10):
            if con1.poll() > 0:
                isData = True;
                break;
            sleep(0.1)
        self.assertTrue(isData) # Should get some data eventually
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertTrue(self.messageCount1 > 0)
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test6_TransferDataFromServerToClient(self):
        """
        In our case, the MAC is the server, and events flow from the server to the Control PC client, so this is the
        most important case.  This test is for a single message.
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con2 = self.createClient(con1) # Connection from client to con1
        con2.startMessageThreadWithCallback(self.receivedMessage2)
        sleep(0.1) # Time for thread start
        self.assertTrue(con2.isWaitingForData)
        self.messageCount2 = 0
        con1.send(self.msg_s2c)
        sleep(0.5)
        con2.stopWaitForData()
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertTrue(self.messageCount2 > 0)
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test7_PingPongTransfer(self):
        """
        Synchronous transfers would include an ACK logic.
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con2 = self.createClient(con1) # Connection from client to con1
        con1.startMessageThreadWithCallback(self.pingPongMessage1)
        con2.startMessageThreadWithCallback(self.pingPongMessage2)
        sleep(0.1) # Time for threads to start
        self.connection1 = con1
        self.connection2 = con2
        self.assertTrue(con1.isWaitingForData)
        self.assertTrue(con2.isWaitingForData)
        self.messageCount1 = 1
        self.messageCount2 = 0
        self.messageBuffer1 = [self.msg_c2s]
        self.messageBuffer2 = []
        con1.send(self.msg_s2c) # Start it out
        sleep(5)  # Wait until all transfers complete
        con1.stopWaitForData()
        con2.stopWaitForData()
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertTrue(self.messageCount1 == MESSAGE_COUNT)
        self.assertTrue(self.messageCount2 == MESSAGE_COUNT)
        for i in range(0, MESSAGE_COUNT):
            self.assertEqual(self.messageBuffer1[i], self.msg_c2s)
            self.assertEqual(self.messageBuffer2[i], self.msg_s2c)
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test8_BidirectionalTransfers(self):
        """
        Asynch transfers in both directions simultaneously.  Due to our logic, sends are atomic, but multiple messages
        can be concatenated and received together.
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con2 = self.createClient(con1) # Connection from client to con1
        con1.startMessageThreadWithCallback(self.receivedMessage1)
        con2.startMessageThreadWithCallback(self.receivedMessage2)
        sleep(0.1) # Time for threads to start
        self.assertTrue(con1.isWaitingForData)
        self.assertTrue(con2.isWaitingForData)
        self.messageCount1 = 0
        self.messageCount2 = 0
        self.messageBuffer1 = []
        self.messageBuffer2 = []
        for i in range(0, MESSAGE_COUNT):
            con1.send(self.msg_s2c)
            con2.send(self.msg_c2s)
        sleep(1)
        con1.stopWaitForData()
        con2.stopWaitForData()
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertTrue(self.messageCount1 == MESSAGE_COUNT)
        self.assertTrue(self.messageCount2 == MESSAGE_COUNT)
        for i in range(0, MESSAGE_COUNT):
            self.assertEqual(self.messageBuffer1[i], self.msg_c2s)
            self.assertEqual(self.messageBuffer2[i], self.msg_s2c)
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test8_BidirectionalTransfersPolled(self):
        """
        Asynch transfers in both directions simultaneously.  Due to our logic, sends are atomic, but multiple messages
        can be concatenated and received together.
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        con1 = self.createServer()
        con2 = self.createClient(con1) # Connection from client to con1
        con1.registerMessageCallback(self.receivedMessage1)
        con2.registerMessageCallback(self.receivedMessage2)
        Thread(target = self.flipFlopPoller, args = (con1, con2)).start()
        self.messageCount1 = 0
        self.messageCount2 = 0
        self.messageBuffer1 = []
        self.messageBuffer2 = []
        for i in range(0, MESSAGE_COUNT):
            con1.send(self.msg_s2c)
            con2.send(self.msg_c2s)
        sleep(10)
        self.isPolling = False # Allow thread to end
        # That's all for now
        con2.close() # Close client first to eliminate "Address in use" error
        con1.close() # Now close the server
        self.assertTrue(self.messageCount1 == MESSAGE_COUNT)
        self.assertTrue(self.messageCount2 == MESSAGE_COUNT)
        for i in range(0, MESSAGE_COUNT):
            self.assertEqual(self.messageBuffer1[i], self.msg_c2s)
            self.assertEqual(self.messageBuffer2[i], self.msg_s2c)
        self.assertEqual(threading.active_count(), g_startThreadCount)

if __name__ == '__main__':
    unittest.main()
