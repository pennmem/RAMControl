import unittest
import inspect
import threading
from time import sleep, time
from RAMControl import RAMControl   # Experiments should only need RAMControl interfaces
from Network import Network         # Low level network interface used only for testing purposes

CONNECTION1 = '165.123.62.49'
CONNECTION2 = '165.123.63.192'
# CONNECTION1 = '192.168.0.60'
# CONNECTION2 = '192.168.0.51'
PORT = 8888
g_startThreadCount = 0

class TestEvent(unittest.TestCase):

    messageCount = 0
    controlPC = None
    lastMessageReceived = None

    def test0_DoFirst(self):
        global g_startThreadCount
        print('***** ' + inspect.stack()[0][3] + ' *****')
        g_startThreadCount = threading.active_count() # Save starting thread count to detect leaks later
        self.assertTrue(True)

    def connectCallback(self, isConnected):
        if isConnected:
            print('Control PC connected')
            self.assertTrue(True)
        else:
            # This simulates a connection from the Control PC
            self.controlPC = Network()
            rtc = self.controlPC.connect(CONNECTION2, CONNECTION1)
            self.assertEqual(rtc, 0)
            sleep(0.5) # Wait for server to connect
            self.controlPC.registerMessageCallback(self.controlPCReceivedMessage)

    def controlPCReceivedMessage(self, message):
        self.messageCount = self.messageCount + 1
        self.lastMessageReceived = message
        print('RECV ControlPC: ' + message)

    def messageReceivedCallback(self, message):
        print('RECV Task Computer: ' + message)

    def sendMessage(self, control, message):
        print('SEND Task Computer: ' + message)
        control.send_message(message)

    def cleanupControlPC(self):
        if self.controlPC != None:
            self.controlPC.stopWaitForData()
            sleep(0.1) # Time for thread to stop

    def test1_TestSendingMessageToControlPC(self):
        """
        Test basic functioning using a loopback: two interfaces to this machine
        """
        global g_startThreadCount
        print('***** ' + inspect.stack()[0][3] + ' *****')
        control = RAMControl()
        # This should work if the indicated IP and PORT exists on the local machine
        if control.initialize(CONNECTION1, PORT, self.messageReceivedCallback) != 0:
            return -1
        rtc = control.connect(self.connectCallback);
        self.assertEqual(rtc, 0)
        self.messageCount = 0;
        msg = 'Task Computer sends test message'
        self.sendMessage(control, msg)
        sleep(0.5) # Give it some time to get there before disconnecting
        control.disconnect()
        self.cleanupControlPC()
        self.assertTrue(self.messageCount == 1)
        self.assertEqual(msg, self.lastMessageReceived)
        self.assertEqual(threading.active_count(), g_startThreadCount)

    def test2_SendEvents(self):
        """
        Send events to Control PC and verify correct format
        """
        global g_startThreadCount
        print '***** ' + inspect.stack()[0][3] + ' *****'
        control = RAMControl()
        # This should work if the indicated IP and PORT exists on the local machine
        if control.initialize(CONNECTION1, PORT, self.messageReceivedCallback) != 0:
            return -1
        rtc = control.connect(self.connectCallback);
        self.assertEqual(rtc, 0)
        millis = int(round(time() * 1000))
        eventType = 'ID';
        eventData = 'UPxxxy'
        control.send_event(millis, eventType, eventData)
        sleep(0.1) # Time for message to be received
        sleep(0.5) # Give it some time to get there before disconnecting
        control.disconnect()
        self.cleanupControlPC()
        (t, tag, data, aux) = control.decode_message(self.lastMessageReceived)
        self.assertEquals(t, millis)
        self.assertEquals(tag, eventType)
        self.assertEquals(data, eventData)
        self.assertEquals(aux, '')
        self.assertEqual(threading.active_count(), g_startThreadCount)
    
    def test3_createMessage(self):
        """
        Tests that JSON message creation is happening properly
        """
        message = RAMControl.build_message(1234, 'DEFINE', ['A', 'B', 'C', 'D'])
        print '***** ' + inspect.stack()[0][3] + ' *****'
        self.assertEqual(message, '{"data": ["A", "B", "C", "D"], "type": "DEFINE", "time": "00000000000000001234"}')

if __name__ == '__main__':
    unittest.main()
