
from time import time, sleep
from threading import Thread
from pyepl.hardware import addPollCallback, removePollCallback

class TestThread:
    """
    Various tests of latency when doing threads versus poll, while waiting for getAnyKey() inside pyEPL.
    Results of running this code indicate that threads cannot be safely used with pyEPL unless the application 
    is in a 'wait' state waiting for user input.  Do not plan on running threads in the background while doing
    any type of processing.  Use of a background 'Network' thread is impossible.  Instead, background tasks
    should be added to pyEPL poll loop, and the poll service functions must be written to quickly service an
    operation and return to the poll loop.  They can't block.
    THIS CODE IS NOT PART OF THE PRODUCTION SYSTEM.
    """
    TESTS = 10 * 60
    INTERVAL = 100000 # 100 milliseconds in microseconds

    def __init__(self):
        self.times = None
        self.beats = 0
        self.nextBeat = 0
        self._isDataReady = False
        self._isPolling = False

    def threadFunctionCorrected(self):
        self.times[0] = t = tnext = time()
        dt = float(TestThread.INTERVAL) / 1000000
        for count in range(TestThread.TESTS):
            tnext += dt
            sleep(tnext - t)
            self.times[count + 1] = t = time()

    def threadFunctionWalks(self):
        self.times[0] = t = time()
        dt = float(TestThread.INTERVAL) / 1000000
        self._isDataReady = False
        for count in range(TestThread.TESTS):
            sleep(dt)
            self.times[count + 1] = time()
        print 'TEST Complete'
        self._isDataReady = True

    def isDataReady(self):
        return self._isDataReady

    def dumpData(self):
        count = 1
        for t in self.times[1:]:
            # ##print str(t - (times[0] + float(count * INTERVAL) / 1000000))
            print str(self.times[count] - self.times[count - 1])
            count += 1

    def startThreadAndReturn(self):
        self.times = (TestThread.TESTS + 1) * [0]
        thread = Thread(target = self.threadFunctionWalks)
        thread.start()
        return

    def doPoll(self):
        if self.beats >= TestThread.TESTS:
            if not self._isDataReady:
                self._isDataReady = True
                self._isPolling = False
                self.cleanupPolling()
                print 'TEST Complete'
                self.dumpData()
            return
        elif self._isPolling:
            t = time()
            if t < self.nextBeat:
                return
            self.beats += 1
            self.times[self.beats] = t
            self.nextBeat = t + float(TestThread.INTERVAL) / 1000000
        else:
            self._isPolling = True
            self.times[0] = time()
            self.beats = 0;
            self.nextBeat = self.times[0] + float(TestThread.INTERVAL) / 1000000

    def doCorrectedPoll(self):
        if self.beats >= TestThread.TESTS:
            if not self._isDataReady:
                self._isDataReady = True
                self._isPolling = False
                self.cleanupPolling()
                print 'TEST Complete'
                self.dumpData()
            return
        elif self._isPolling:
            t = time()
            if t < self.nextBeat:
                return
            self.beats += 1
            self.times[self.beats] = t
            self.nextBeat += float(TestThread.INTERVAL) / 1000000
        else:
            self._isPolling = True
            self.times[0] = time()
            self.beats = 0;
            self.nextBeat = self.times[0] + float(TestThread.INTERVAL) / 1000000

    def setupPolling(self):
        self.times = (TestThread.TESTS + 1) * [0]
        self.count = 0
        self._isPolling = False
        self._isDataReady = False
        addPollCallback(self.doCorrectedPoll)

    def cleanupPolling(self):
        removePollCallback(self.doCorrectedPoll)

    def createThread(self):
        thread = self.startThreadAndReturn()
        thread.join()
        self.dumpData()

if __name__ == '__main__':
    test = TestThread()
    test.createThread()
