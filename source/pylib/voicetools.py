"""Tools for voice activity detection (VAD) for FR5 and related tasks."""

from __future__ import division

from io import BytesIO
import wave
import audioop
from collections import namedtuple
import logging

import numpy as np

logger = logging.getLogger(__name__)

AudioFrame = namedtuple("AudioFrame", "data, timestamp, duration")


def apodize(data, window=5, rate=16000):
    """Apply a Hamming window to reduce a sound's 'click' onset / offset.

    :param np.ndarray data: Audio data.
    :param int window: Window size in ms.
    :param int rate: Audio frame rate in Hz.

    """
    hw_size = int(min(rate // (1000 / window), len(data) // 15))
    hamming_window = np.hamming(2 * hw_size + 1)
    data[:hw_size] *= hamming_window[:hw_size]
    data[-hw_size:] *= hamming_window[-hw_size:]
    return data


def frame_generator(audio, frame_duration=30):
    """A generator to get audio frames of specific length in time.

    Note factors of 2 are (probably?) hard-coded values indicating sample width
    (i.e., 16-bit).

    :param bytes audio: Audio data.
    :param int frame_duration: Frame duration in ms.

    """
    wav = wave.open(BytesIO(audio))
    sample_rate = wav.getframerate()
    n = int(sample_rate * (frame_duration / 1000.) * 2)  # number of frames
    duration = n / wav.getframerate() / 2.0
    offset = 0
    timestamp = 0.0
    while offset + n < len(audio):
        yield AudioFrame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


def downsample(buf, outrate=16000, window=5):
    """Downsample audio. Required for voice detection.

    :param BytesIO buf: Audio data buffer.
    :param int outrate: Output audio sample rate in Hz.
    :param int window: Window size in ms (0 to disable windowing).
    :returns: Output buffer.
    :rtype: BytesIO

    """
    frames = buf.read()

    # Convert to mono
    if True:  # inpars.nchannels == 2:
        #frames = audioop.tomono(frames, inpars.sampwidth, 1, 1)
        frames = audioop.tomono(frames, 2, 1, 1)

    # Convert to 16-bit depth
    if False:  # inpars.sampwidth > 2:
        #frames = audioop.lin2lin(frames, inpars.sampwidth, 2)
        frames = audioop.lin2lin(frames, 2, 2)

    # Convert frame rate to 16000 Hz
    # frames, _ = audioop.ratecv(frames, 2, 1, inpars.framerate, outrate, None)
    frames, _ = audioop.ratecv(frames, 2, 1, 22050, outrate, None)

    # Apply window function
    if window > 0:
        data = apodize(np.fromstring(frames, dtype=np.int16).astype(float),
                       window=window)
        frames = data.tostring()  # really bytes

    # Return a BytesIO version of the output
    outbuf = BytesIO()
    out = wave.open(outbuf, "wb")
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(outrate)
    out.writeframes(frames)
    out.close()

    outbuf.seek(0)
    return outbuf
