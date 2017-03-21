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
from multiprocessing import Process, Queue, Event, Pipe, current_process
from threading import Thread
import logging
import wave
import traceback as tb

from pyaudio import PyAudio, paInt16
from webrtcvad import Vad
from logserver import create_logger

from . import ipc
from .exc import WrongProcessError

SAMPLE_RATE = 32000
FRAMES_PER_BUFFER = 4096


class VoiceServer(Process):
    """A server that monitors the microphone for voice activity.

    :param Pipe pipe: A pipe for communicating with the parent process.
    :param int vad_level: webrtcvad VAD aggressiveness (0, 1, 2, or 3; higher is
        more aggressive at filtering out non-speech).
    :param int consecutive_frames: The number of frames in a row that register
        as speech to consider it actually speech (to try to minimize
        transients).
    :param str filename: WAV file to read for testing (doesn't use microphone).
        Note that this will actually play the WAV file.
    :param int loglevel: Logging level to use. If None, assume ``logging.INFO``.

    """
    def __init__(self, pipe, vad_level=3, consecutive_frames=3, filename=None,
                 loglevel=logging.INFO):
        super(VoiceServer, self).__init__()

        self.pipe = pipe
        self.vad_aggressiveness = vad_level
        self.consecutive_frames = consecutive_frames
        self.filename = filename
        self.logger = logging.getLogger()  # to be redefined once the process starts; tests fail otherwise
        self.loglevel = loglevel

        self.data_queue = Queue()
        self.stop_stream = Event()
        self.done = Event()

    def check_for_speech(self, frame_duration_ms=20):
        """Checks for speech.

        :param int frame_duration_ms: Audio frame length in ms.

        """
        vad = Vad(self.vad_aggressiveness)
        speaking = False  # to keep track of if vocalization ongoing

        n = int(SAMPLE_RATE * (frame_duration_ms / 1000.) * 2)
        # duration = n / SAMPLE_RATE / 2.0

        last_timestamp_sent = 0

        while not self.done.is_set():
            chunk = self.data_queue.get()

            offset = 0
            framecount = []
            while offset + n < len(chunk):
                now = time.time() * 1000.0  # caveat: this is not the same as PyEPL's clock...
                frame = chunk[offset:offset + n]
                if vad.is_speech(frame, SAMPLE_RATE):
                    framecount.append({"timestamp": now})

                    if len(framecount) >= self.consecutive_frames and not speaking:
                        speaking = True
                        payload = {
                            "speaking": True,
                            "timestamp": framecount[0]["timestamp"]
                        }
                        self.pipe.send(ipc.message("VOCALIZATION", payload))
                        self.logger.debug("Started speaking at %f", now)
                else:
                    if speaking:
                        speaking = False
                        payload = {
                            "speaking": False,
                            "timestamp": now
                        }
                        self.pipe.send(ipc.message("VOCALIZATION", payload))
                        self.logger.debug("Stopped speaking at %f", now)
                    framecount = []

                offset += n

            now = time.time() * 1000
            if now - last_timestamp_sent >= 1000:
                self.pipe.send(ipc.message("TIMESTAMP", dict(timestamp=now)))
                last_timestamp_sent = now

    def quit(self):
        """Terminate the process."""
        if not self.done.is_set():
            self.logger.info("Shutting down voice server...")
            self.done.set()
        else:
            self.logger.error("Voice server already shut down!")

    def open_audio_stream(self, audio):
        """Open the audio stream.

        :returns: stream, wav

        """
        wav = None

        try:
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
            return stream, wav
        except:
            self.pipe.send(ipc.critical_error_message("Failed to open audio stream"))
            raise

    def read_audio_stream(self, stream, wav=None):
        """Reads from the audio stream and queues data for VAD.

        :param stream: Audio input stream.
        :param wav: Wave data for writing to stream (if simulating).

        """
        while not self.stop_stream.is_set():
            try:
                if wav is None:
                    data = stream.read(FRAMES_PER_BUFFER)
                else:
                    data = wav.readframes(FRAMES_PER_BUFFER)
                    if len(data) is 0:
                        self.quit()
                        continue
                    stream.write(data)
                self.data_queue.put(data)
            except IOError:
                # TODO: real error handling
                self.logger.critical("Exception in voiceserver", exc_info=True)
                self.pipe.send(ipc.critical_error_message("IOError"))
            except:
                self.logger.error("Unknown error", exc_info=True)

        stream.close()
        self.stop_stream.clear()

    def run(self):
        self.logger = create_logger("voiceserver", level=self.loglevel)

        audio = PyAudio()

        vad_thread = Thread(target=self.check_for_speech)
        vad_thread.daemon = True
        vad_thread.start()
        mic_thread = None  # later, the thread to read from the mic

        while not self.done.is_set():
            try:
                msg = self.pipe.recv()  # Blocks until message sent

                if msg["type"] == "START":
                    self.logger.info("Got request to start VAD")
                    stream, wav = self.open_audio_stream(audio)
                    mic_thread = Thread(target=self.read_audio_stream,
                                        args=(stream, wav))
                    mic_thread.start()
                    self.pipe.send(ipc.message("STARTED"))

                elif msg["type"] == "STOP":
                    self.logger.info("Got request to stop VAD")
                    self.stop_stream.set()
                    self.pipe.send(ipc.message("STOPPED"))

                else:
                    self.logger.error("Unexpected message type received. Message: %s", msg)
                    continue
            except EOFError:
                self.logger.warning("Broken pipe")
                self.quit()
                continue

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

    parent, child = Pipe()
    p = VoiceServer(child, filename=args.filename,
                    loglevel=levels[args.loglevel])
    p.start()

    parent.send(ipc.message("START"))
    parent.recv()
    try:
        while True:
            if parent.poll():
                data = parent.recv()
                if data["type"] != "TIMESTAMP":
                    print(data)
    except KeyboardInterrupt:
        parent.send(ipc.message("STOP"))


if __name__ == "__main__":
    main()
