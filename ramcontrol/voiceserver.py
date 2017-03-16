"""
Installation notes
------------------

PyAudio relies on portaudio. To install on mac::

  $ brew install portaudio
  $ CPATH=/usr/local/include LIBRARY_PATH=/usr/local/lib pip install pyaudio

"""

from __future__ import print_function, division

import os.path as osp
import time
from argparse import ArgumentParser
from multiprocessing import Process, Queue, Event, current_process
from threading import Thread
import logging
import wave

from pyaudio import PyAudio, paInt16
from webrtcvad import Vad
from logserver import create_logger
import zmq

from .exc import WrongProcessError

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
    :param int loglevel: Logging level to use. If None, assume ``logging.INFO``.

    """
    def __init__(self, sock_addr="tcp://127.0.0.1:9898", vad_level=3,
                 consecutive_frames=3, filename=None, loglevel=logging.INFO):
        super(VoiceServer, self).__init__()

        self.addr = sock_addr
        self.vad_aggressiveness = vad_level
        self.consecutive_frames = consecutive_frames
        self.filename = filename
        self.logger = None  # to be defined once the process starts
        self.loglevel = loglevel

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
        self.logger.debug("Connecting to address %s", self.addr)

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
                        self.logger.debug("Started speaking at %f", now)
                else:
                    if speaking:
                        speaking = False
                        socket.send_json({
                            "state": "VOCALIZATION",
                            "value": False,
                            "timestamp": now
                        })
                        self.logger.debug("Stopped speaking at %f", now)
                    framecount = []

                offset += n

    def quit(self):
        """Terminate the process."""
        if not self.done.is_set():
            self.logger.info("Shutting down voice server...")
            self.done.set()
        else:
            self.logger.error("Voice server already shut down!")

    def run(self):
        ctx = zmq.Context()

        audio = PyAudio()
        wav = None

        self.logger = create_logger("voiceserver", level=self.loglevel)

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
            except IOError:
                # TODO: real error handling
                self.logger.error("Exception in voiceserver", exc_info=True)
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt detected")
                self.quit()
            except:
                self.logger.error("Unknown error", exc_info=True)

        if stream is not None:
            stream.close()
        audio.terminate()


def main():
    """Run a standalone VoiceServer."""
    levels = {
        "info": logging.INFO,
        "debug": logging.DEBUG,
        "warning": logging.WARNING
    }

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-f", "--filename", default=None, type=str,
                        help="Path to wav file as input")
    parser.add_argument("-l", "--loglevel", choices=levels, default="info",
                        help="Log level")

    args = parser.parse_args()

    p = VoiceServer(filename=args.filename, loglevel=levels[args.loglevel])
    p.start()
    try:
        p.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
