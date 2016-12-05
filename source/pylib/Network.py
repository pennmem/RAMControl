'''
Network interfaces
'''
import socket
from time import sleep
from threading import Thread
import ctypes


def exception_msg(msg, err):
    """ Extract message from an exception """
    if len(err.args) == 1:
        return msg + ' : ' + err[0]
    else:
        return msg + ': Error: ' + str(err[0]) + ': ' + err[1]


class Network:

    DEFAULT_HOST = '192.168.137.200'        # Wired LAN connection on this Task Computer
    DEFAULT_PORT = 8888
    RECV_BUFFER = 1024

    def __init__(self):
        """ Constructor """
        self.toHost = None                  # The Task Computer IP address (me)
        self.fromHost = None                # The client IP address.  During testing, it's possible for this to be
                                            # a wireless IP on the Task Computer
        self.port = 0                       # Will eventually be replace by DEFAULT_PORT or some other valid port
        self.sk = None                      # Name the variable that saves the socket information something different
                                            # from the module 'socket'
        self.connection = None              # Returned from 'accept'.  Probably could be local
        self.address = None                 # Returned from 'accept'.  Probably could be local
        self.waitForConnectionThread = None # Connection thread handle
        self.waitForDataThread = None       # Indicates wait for data is active
        self.receiveDataCallback = None     # Function called when a message is received

        # Properties exposed through getters/setters.  These should NOT be accessed directly
        self._isConnected = False           # True when a connection is established
        self._isListening = False           # True when the server (me) is waiting for a connection
        self._isWaitingForData = False      # True when a connection exists and the server is waiting for data

    def isConnected(self):
        """ Return True if a connection exists """
        return self._isConnected

    def isListening(self):
        """ Return True if the server is listening, but the client has not yet connected """
        return self._isListening

    def isWaitingForData(self):
        """ Return True if thread is ready and waiting for data """
        return self._isWaitingForData

    def getAlternateInterfaces(self):
        """
        Return a list of interfaces that are supported on this computer.
        """
        return socket.getaddrinfo(socket.gethostname(), Network.DEFAULT_PORT, socket.AF_INET, socket.SOCK_STREAM)

    def open(self, host=None, port=0):
        """
        Open a connection to the indicated host at the specified port.
        Return Success(0), or Error(non-zero)
        """
        self.toHost = host or self.DEFAULT_HOST
        self.port = port or self.DEFAULT_PORT

        # self.sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log('Socket created for %s:%d' % (self.toHost, self.port))

        # Bind socket to the specified host and port
        try:
            # self.sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sk.bind((self.toHost, self.port))
        except socket.error as err:
            self.log(exception_msg('Bind failed', err))
            return -1

        self.log('Socket bind complete %s:%d' % (self.toHost, self.port))
        return 0

    class timeval(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]

    def listen(self):
        """
        Wait to accept a connection.  Since this is blocking, this method is normally called from a thread.
        Returns success (0) or error (non-zero)
        """
        if self._isConnected or self._isListening:
            return -1 # Should not be calling if already open or waiting for connection
        self._isConnected = False
        # self.sk.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
        # self.sk.listen(1)  # Accept a single connection only
        self.log("Socket is listening")

        try:
            self._isListening = True
            self.sk.setblocking(True)

            self.connection, self.address = self.sk.accept()
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, self.timeval(0, 1000))
            # self.connection.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
            self.connection.setblocking(True)
        except socket.error as err:
            self._isListening = False
            self.log(exception_msg('Socket exception accepting connection', err))
            return -2
        except Exception as err:
            self._isListening = False
            self.log(exception_msg('General exception accepting connection', err))
            return -3

        self.log('Connected from ' + self.address[0] + ' to ' + self.toHost + ':' + str(self.address[1]))
        self.fromHost = self.address[0]
        self._isConnected = True
        self._isListening = False
        return 0

    def connect(self, fromHost = None, toHost = None, port = 0):
        """
        Connect from a client to a server that (should be) ready for the connection.
        Since the Task Computer is the 'server' in the pair of socket connections, this
        method is used by DummyClient.py but not by the Task Computer.
        """
        # Supply defaults
        if toHost == None:
            toHost = socket.gethostname()
        if port == 0:
            port = Network.DEFAULT_PORT
        self.toHost = toHost
        self.port = port

        rtc = 0
        try:
            # Create a stream socket
            self.sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.log('Socket created for %s:%d' % (self.toHost, self.port))
            # Allow for binding to a specific host to allow testing with multiple NICs on same machine
            if fromHost != None:
                self.sk.bind((fromHost, 0))
            self.sk.settimeout(5) # Should be plenty for hardwired sockets
            self.sk.connect((self.toHost, self.port))
            self.sk.settimeout(None)
            self.sk.setblocking(0) # Set to non-blocking
        except socket.error as err:
            self.log(exception_msg('Socket exception connecting', err))
            rtc = -1
        except Exception as err:
            self.log(exception_msg('General exception connecting', err))
            rtc = -2
        else:
            self.log("Connection made to : %s:%d" % (self.toHost, self.port))
        return rtc

    def poll(self):
        """
        Poll for data and call receiveDataCallback when this occurs.
        Note:  If socket is setup for non-blocking mode, this function returns immediately
        Returns: No data (0), data received (1), error (negative)
        """
        try:
            if self._isConnected:  # Indicates this is a server-side receive
                data = self.connection.recv(Network.RECV_BUFFER)
            else:
                data = self.sk.recv(Network.RECV_BUFFER)
            if len(data) > 0:
                self.log("Received: " + data)
                if self.receiveDataCallback != None:
                    self.receiveDataCallback(data)
                return 1
        except socket.error as err:
            if err[0] != 35:  # OK - No data for non-blocking recv()
                self.log(exception_msg('Socket exception transferring data', err))
                return -1
        except Exception as err:
            self.log(exception_msg('General exception transferring data:', err))
            return -2
        return 0

    def receive(self):
        """
        Receive data and call the indicated callback when this occurs
        This is a thread function that should be terminated by setting 'isWaitingForData' to False
        """
        self.isWaitingForData = True  # This can be set externally to gracefully terminate the thread
        while self.isWaitingForData:
            rtc = self.poll()
            if 0 == rtc:
                sleep(.001) # This should be OK, since we are on a thread and very little (or no) data is received by this computer
            elif rtc < 0:
                break # on error break out of loop
            # Otherwise, we received and processed a message. Stay in loop

    def old_send(self, message):
        """
        Send a message to the client.  This is a blocking call, but should be very quick for short messages.
        Returns Connection Broken (-1), characters transmitted (n>=0)
        """
        total = 0
        self.log('Sending message: ' + message)
        msglen = len(message)
        while total < msglen:
            try:
                if self._isConnected: # Indicates this is a server-side send
                    sent = self.connection.send(message)
                else:   # This is a client-side send
                    sent = self.sk.send(message)
                self.log('Sent ' + str(sent) + ' bytes')
            except socket.error as err:
                sent = 0
                if err[0] != 32: # Broken pipe
                    self.log(exception_msg('Socket exception sending data', err))
            except Exception as err:
                self.log(exception_msg('General exception sending data:', err))
                break
            if sent == 0:
                self._isConnected = False
                self.log('Connection broken')
                return -1 # Connection broken
            total = total + sent
        self.log('Send message complete')
        return total

    def send(self, message):
        """
        Send a message to the client.  This is a blocking call, but should be very quick for short messages.
        Returns Connection Broken (-1), characters transmitted (n>=0)
        """
        total = 0
        self.log('Sending message: ' + message)
        msglen = len(message)
        try:
            if self._isConnected: # Indicates this is a server-side send
                sent = self.connection.send(message)
            else:   # This is a client-side send
                sent = self.sk.send(message)
            self.log('Sent ' + str(sent) + ' bytes')
        except socket.error as err:
            sent = 0
            if err[0] != 32: # Broken pipe
                self.log(exception_msg('Socket exception sending data', err))
        except Exception as err:
            sent = 0
            self.log(exception_msg('General exception sending data:', err))
        if sent == 0:
            self._isConnected = False
            self.log('Connection broken')
            return -1 # Connection broken
        total = total + sent
        self.log('Send message complete')
        return total

    def close(self):
        """
        Close the connection and reset all flags
        Since there is little that can be done if a failure occurs, don't return a value
        """
        try:
            if self._isConnected:
                self.sk.shutdown(socket.SHUT_RDWR) # Inform the other side that we are about to close
                sleep(0.1) # Time for other end to take the appropriate action
            self.sk.close()
        except socket.error as err:
            if err[0] != 57:
                self.log(exception_msg('Socket exception closing', err))
            else: # Expect this and retry
                try:
                    sleep(0.1)
                    self.sk.close()
                except socket.error as err2:
                    self.log(exception_msg('Socket close retry exception', err2))
                else:
                    self.log('Close successful after retry')
        except Exception as err:
            self.log(exception_msg('Problem closing socket', err))
        else:
            self.log("Socket closed")
        self._isConnected = False
        self._isListening = False

    def waitForConnection(self):
        """
        Call this method to start a thread that waits for a connection.  This method does not block.
        Use isConnected() and isWaitForConnection() to determine the state of the connection
        Return Thread already exists (-1), or thread created successfully (0).

        NOTE: There is no easy way to terminate the 'listen' function, so it is possible this will leak threads.
              However, this is only remotely possible, since the idea of creating a server is for a client to connect to it.
        """
        if self.waitForConnectionThread != None and self.waitForConnectionThread.isAlive():
            return -1
        self.waitForConnectionThread = Thread(target = self.listen) # First argument is function to be run,
                                                                    # second is tuple of arguments to function
        self.waitForConnectionThread.start()
        return 0

    def startReceiveThread(self):
        """
        Create a single wait for data thread.
        Normally there is no need to call this method, since it is called by waitForMessage()
        """
        if self.waitForDataThread == None or not self.waitForDataThread.isAlive():
            self.waitForDataThread = Thread(target = self.receive)
            self.waitForDataThread.start()

    def stopWaitForData(self):
        """
        Call this method to request nice termination of the waitForDataThread
        """
        if self.waitForDataThread != None and self.waitForDataThread.isAlive():
            self.isWaitingForData = False
            self.waitForDataThread.join(10)  # If thread doesn't quit in a reasonable time, bail out

    def registerMessageCallback(self, callback):
        """
        Register the callback
        """
        self.receiveDataCallback = callback

    def startMessageThreadWithCallback(self, callback = None):
        """
        Register a callback for data received, and if receive thread is not started yet, start it.
        """
        if callback != None:
            self.registerMessageCallback(callback)
        if self.waitForDataThread == None or not self.waitForDataThread.isAlive():
            self.startReceiveThread()

    def log(self, msg):
        """ Common point for messages.  Comment out below code to display them or ignore them """
        # print msg
