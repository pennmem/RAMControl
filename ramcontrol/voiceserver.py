"""
Installation notes
------------------

PyAudio relies on portaudio. To install on mac::

  $ brew install portaudio
  $ CPATH=/usr/local/include LIBRARY_PATH=/usr/local/lib pip install pyaudio

"""

from __future__ import print_function, division

import time
from multiprocessing import Process, Queue, Event, current_process
from threading import Thread
import logging
import wave

from pyaudio import PyAudio, paInt16
from webrtcvad import Vad

import zmq

from .exc import WrongProcessError

# TODO: implement real logging
# see https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAMES_PER_BUFFER = 1024


class VoiceServer(Process):
    """A server that monitors the microphone for voice activity.

    :param str sock_addr: Socket to connect to to publish vocalization events
        to.
    :param int vad_level: webrtcvad VAD aggressiveness (0, 1, 2, or 3; higher is
        more aggressive at filtering out non-speech).
    :param int consecutive_frames: The number of frames in a row that register
        as speech to consider it actually speech (to try to minimize
        transients).
    :param str filename: WAV file to read for testing (doesn't use microphone).
        Note that this will actually play the WAV file.

    """
    def __init__(self, sock_addr="tcp://127.0.0.1:9898", vad_level=3,
                 consecutive_frames=3, filename=None):
        super(VoiceServer, self).__init__()

        self.addr = sock_addr
        self.vad_aggressiveness = vad_level
        self.consecutive_frames = consecutive_frames
        self.filename = filename

        self.queue = Queue()
        self.done = Event()

    def make_listener_socket(self, ctx):
        """Return a bound socket for the :class:`VoiceServer` instance to
        connect to.

        :param zmq.Context ctx:
        :returns: socket
        :rtype: zmq.Socket
        :raises WrongProcessError: when calling from a subprocess.

        """
        if current_process().name != "MainProcess":
            raise WrongProcessError("Only call make_listener_socket from the main process!")
        protocol, _, port = self.addr.split(":")
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.bind("{}://*:{}".format(protocol, port))
        return socket

    def check_for_speech(self, ctx, frame_duration_ms=20):
        """Checks for speech.

        :param zmq.Context ctx: ZMQ context for creating a PUB socket.
        :param int frame_duration_ms: Audio frame length in ms.

        """
        socket = ctx.socket(zmq.PUB)
        socket.connect(self.addr)
        logger.debug("Connecting to address %s", self.addr)

        vad = Vad(self.vad_aggressiveness)
        speaking = False  # to keep track of if vocalization ongoing

        n = int(SAMPLE_RATE * (frame_duration_ms / 1000.) * 2)
        # duration = n / SAMPLE_RATE / 2.0

        while not self.done.is_set():
            chunk = self.queue.get()

            offset = 0
            framecount = []
            while offset + n < len(chunk):
                now = time.time() * 1000.0  # caveat: this is not the same as PyEPL's clock...
                frame = chunk[offset:offset + n]
                if vad.is_speech(frame, SAMPLE_RATE):
                    framecount.append({"timestamp": now})

                    if len(framecount) >= self.consecutive_frames and not speaking:
                        speaking = True
                        socket.send_json({
                            "state": "VOCALIZATION",
                            "value": True,
                            "timestamp": framecount[0]["timestamp"]
                        })
                        logger.debug("Started speaking at %f", now)
                else:
                    if speaking:
                        speaking = False
                        socket.send_json({
                            "state": "VOCALIZATION",
                            "value": False,
                            "timestamp": now
                        })
                        logger.debug("Stopped speaking at %f", now)
                    framecount = []

                offset += n

    def quit(self):
        """Terminate the process."""
        if not self.done.is_set():
            logger.info("Shutting down voice server...")
            self.done.set()
        else:
            logger.error("Voice server already shut down!")

    def run(self):
        ctx = zmq.Context()

        audio = PyAudio()
        wav = None

        # We're live
        if self.filename is None:
            stream = audio.open(
                format=paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=FRAMES_PER_BUFFER,
                input_device_index=None  # None uses the system default input device
            )

        # We're testing
        else:
            wav = wave.open(self.filename)
            stream = audio.open(
                format=audio.get_format_from_width(wav.getsampwidth()),
                channels=wav.getnchannels(),
                rate=wav.getframerate(),
                output=True
            )

        vad_thread = Thread(target=self.check_for_speech, args=(ctx,))
        vad_thread.daemon = True
        vad_thread.start()

        try:
            while not self.done.is_set():
                try:
                    if wav is None:
                        data = stream.read(FRAMES_PER_BUFFER)
                    else:
                        data = wav.readframes(FRAMES_PER_BUFFER)
                        if len(data) is 0:
                            self.quit()
                            continue
                        stream.write(data)
                    self.queue.put(data)
                except Exception as e:
                    # TODO: real error handling
                    print(e)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt detected")
            self.quit()
        finally:
            if stream is not None:
                stream.close()
            audio.terminate()


if __name__ == "__main__":
    import os.path as osp
    from util import data_path

    logging.basicConfig(level=logging.DEBUG)
    p = VoiceServer(filename=osp.join(data_path(), "one-two-three.wav"))
    p.start()
    try:
        p.join()
    except KeyboardInterrupt:
        pass
