"""Tools for voice activity detection (VAD) for FR5 and related tasks."""

from __future__ import division

import struct
from io import BytesIO
import wave
import audioop
from collections import namedtuple
import logging

import numpy as np
from scipy.signal import butter, lfilter

from pyepl import timing
import pyepl.sound

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


def rms(data):
    """Basic audio-power measure: root-mean-square of data.
    Identical to `std` when the mean is zero; faster to compute just rms.
    """
    if data.dtype == np.int16:
        md2 = data.astype(np.float) ** 2  # int16 wrap around --> negative
    else:
        md2 = data ** 2
    return np.sqrt(np.mean(md2))


def smooth(data, win=16, tile=True):
    """Running smoothed average, via convolution over `win` window-size.
    `tile` with the mean at start and end by default; otherwise replace with 0.
    """
    weights = np.ones(win) / win
    data_c = np.convolve(data, weights)[win - 1:-(win - 1)]
    if tile:
        pre = np.tile(data_c[0], win // 2)
        post = np.tile(data_c[-1], win // 2)
    else:
        pre = post = np.zeros(win // 2)
    data_pre_c = np.concatenate((pre, data_c))
    data_pre_c_post = np.concatenate((data_pre_c, post))
    return data_pre_c_post[:len(data)]


def bandpass_filter(data, low=2000, high=8000, rate=44100, order=6):
    """Bandpass filter the data.

    :param np.ndarray data:
    :param float low:
    :param float high:
    :param flaot rate:
    :param int order:

    """
    return BandpassFilter.filter(data, low, high, rate, order)


def zero_crossings(data):
    """Return a vector of length n-1 of zero-crossings within vector `data`.
    1 if the adjacent values switched sign, or
    0 if they stayed the same sign.
    """
    zx = np.zeros(len(data))
    zx[np.where(data[:-1] * data[1:] < 0)] = 1
    return zx


def apodize(data, ms=5, rate=44100):
    """Apply a Hamming window (5ms) to reduce a sound's 'click' onset / offset.
    """
    hw_size = int(min(rate // (1000 / ms), len(data) // 15))
    hamming_window = np.hamming(2 * hw_size + 1)
    data[:hw_size] *= hamming_window[:hw_size]
    data[-hw_size:] *= hamming_window[-hw_size:]
    return data


class AudioTrack(pyepl.sound.AudioTrack):
    """Extended PyEPL :class:`AudioTrack` to add VAD support.

    This adds the following parameters:

     * ``speaking`` - a flag indicating a vocalization is happening
     * ``rec_interval`` - amount of time in ms to record and listen for
       vocalization

    """
    _vad_threshold = 10

    def __init__(self, *args, **kwargs):
        super(AudioTrack, self).__init__(*args, **kwargs)
        self.speaking = False
        self.rec_interval = 20

    def __recCallback__(self):
        """Modify the normal __recCallback__ to determine and update speech
        onsets/offsets. This needs to occur fast enough (i.e., fast enough to
        not disrupt the polling operations).

        This is a horrific hack, but then again, so is PyEPL.

        """
        currentTime = timing.now()
        if self.recording and currentTime >= self.last_rec + self.rec_interval:
            newstuff = self.getBuffData()

            # Update the last time
            self.last_rec = currentTime

            if len(newstuff) > 0:
                # append the data to the clip
                self.recClip.append(newstuff, self.eplsound.getRecChans())

        # VAD code inserted here
        ########################

        xbuff = np.array(struct.unpack(str(len(newstuff) / 2) + 'h', newstuff),
                         dtype=np.int16)
        xbuff = xbuff[::2]

        loudness = rms(bandpass_filter(xbuff))
        conditions = all([loudness > self._vad_threshold])

        # TODO: send state messages to host PC
        if not self.speaking and conditions:  # vocalization start
            self.speaking = True
            self.logMessage("%s\t%s" % ("SP", "Start"), currentTime)
        elif self.speaking and not conditions:  # vocalization end
            self.speaking = False
            self.logMessage("%s\t%s" % ("SP", "Stop"), currentTime)


AudioFrame = namedtuple("AudioFrame", "bytes, timestamp, duration")


def frame_generator(audio, frame_duration, sample_rate):
    """A generator to get audio frames of specific length in time.

    :param BytesIO audio: Audio data.
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

    :param buf: Audio data buffer (or path to WAV file).
    :param int outrate: Output audio sample rate in Hz.
    :returns: Output buffer.
    :rtype: BytesIO

    """
    wav = wave.open(buf)
    inpars = wav.getparams()
    frames = wav.readframes(inpars.nframes)

    # Convert to mono
    if inpars.nchannels == 2:
        frames = audioop.tomono(frames, inpars.sampwidth, 1, 1)

    # Convert to 16-bit depth
    if inpars.sampwidth > 2:
        frames = audioop.lin2lin(frames, inpars.sampwidth, 2)

    # Convert frame rate to 16000 Hz
    frames, _ = audioop.ratecv(frames, 2, 1, inpars.framerate, outrate, None)

    # Return a BytesIO version of the output
    outbuf = BytesIO()
    out = wave.open(outbuf, "w")
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(outrate)
    out.writeframes(frames)
    out.close()
    outbuf.seek(0)
    return outbuf
