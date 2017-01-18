"""Tools for voice activity detection (VAD) for FR5 and related tasks."""

from __future__ import division
import logging
import numpy as np
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
