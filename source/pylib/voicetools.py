"""Tools for voice activity detection (VAD) for FR5 and related tasks."""

from __future__ import division

from io import BytesIO
import os.path as osp
import wave
import audioop
from collections import namedtuple
import logging

from scipy.signal import butter, lfilter

logger = logging.getLogger(__name__)


class BandpassFilter(object):
    """Convenience class to perform audio bandpass filtering.

    This implements a cached version of a Butterworth bandpass filter. To
    pre-populate the cache, make sure to call the :meth:`precache_butter`
    class method.

    Apart from pre-caching, this class doesn't need to be instantiated or have
    its methods called from elsewhere. Instead, use the :func:`bandpass_filter`
    function.

    """
    _butter_cache = {}

    @staticmethod
    def _cached_butter(order, band, rate=44100):
        """Caching version of :func:`scipy.signal.butter`. Allows faster
        band-pass filtering during real-time processing.

        TODO: make band into two separate parameters

        :param int order: Order of the filter.
        :param tuple band: Length-2 tuple specifying the low and high critical
            frequencies
        :param float rate:

        """
        _h = hash((order, band, rate))
        if _h not in BandpassFilter._butter_cache:
            low, high = band
            nyqfreq = float(rate) / 2
            lowf = low / nyqfreq
            highf = high / nyqfreq
            BandpassFilter._butter_cache[_h] = butter(order, (lowf, highf), btype='bandpass')
        return BandpassFilter._butter_cache[_h]

    @classmethod
    def precache_butter(cls, lows=(80, 100, 120), highs=(1200, 3000, 8000),
                        bands=((2000, 8000),),  # content-filtered speech
                        rate=44100):
        """Pre-cache some useful (b, a) values.

        :param list lows: Low frequency cutoffs.
        :param list highs: High frequency cutoffs.
        :param list bands: FIXME
        :param float rate: FIXME

        """
        for low in lows:
            for high in highs:
                BandpassFilter._cached_butter(6, (low, high), rate=rate)
        for band in bands:
            BandpassFilter._cached_butter(6, band, rate=rate)

    @staticmethod
    def filter(data, low=2000, high=8000, rate=44100, order=6):
        """Return bandpass filtered `data`.

        :param np.ndarray data:
        :param float low:
        :param float high:
        :param flaot rate:
        :param int order:

        """
        b, a = BandpassFilter._cached_butter(order, (low, high), rate)
        return lfilter(b, a, data)


AudioFrame = namedtuple("AudioFrame", "bytes, timestamp, duration")


def frame_generator(audio, frame_duration, sample_rate):
    """A generator to get audio frames of specific length in time.

    :param bytes audio: Audio data.
    :param int frame_duration: Frame duration in ms.
    :param int sample_rate: Audio sample rate in Hz.

    """
    AudioFrame = namedtuple("AudioFrame", "bytes, timestamp, duration")

    n = int(sample_rate * (frame_duration / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield AudioFrame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


def downsample(buf, outrate=16000):
    """Downsample audio. Required for voice detection.

    :param BytesIO buf: Audio data buffer.
    :param int outrate: Output audio sample rate in Hz.
    :returns: Output buffer.
    :rtype: BytesIO

    """
    #wav = wave.open(buf)
    #inpars = wav.getparams()
    #frames = wav.readframes(inpars.nframes)
    frames = buf.read()

    # Convert to mono
    if True:  # inpars.nchannels == 2:
        #frames = audioop.tomono(frames, inpars.sampwidth, 1, 1)
        frames = audioop.tomono(frames, 2, 1, 1)

    # Convert to 16-bit depth
    if True:  # inpars.sampwidth > 2:
        #frames = audioop.lin2lin(frames, inpars.sampwidth, 2)
        frames = audioop.lin2lin(frames, 2, 2)

    # Convert frame rate to 16000 Hz
    # frames, _ = audioop.ratecv(frames, 2, 1, inpars.framerate, outrate, None)
    frames, _ = audioop.ratecv(frames, 2, 1, 22050, outrate, None)

    # Return a BytesIO version of the output
    outbuf = BytesIO()
    out = wave.open(outbuf, "w")
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(outrate)
    out.writeframes(frames)
    out.close()

    # TODO: Debugging only... remove!
    out = wave.open(osp.expanduser("~/tmp/out.wav"), "w")
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(outrate)
    out.writeframes(frames)
    out.close()

    outbuf.seek(0)
    return outbuf
