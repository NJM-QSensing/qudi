import matplotlib.pyplot as plt
import TimeTagger
import numpy as np
import numba
from time import sleep


class VisibilitySlope(TimeTagger.CustomMeasurement):
    """
    Example for a single start - multiple stop measurement.
        The class shows how to access the raw time-tag stream.
    """

    def __init__(self, tagger, click_channel, start_channel, binwidth):
        TimeTagger.CustomMeasurement.__init__(self, tagger)
        self.click_channel = click_channel
        self.start_channel = start_channel
        self.start_channel_2 = -start_channel
        self.binwidth = binwidth
        self.max_bins = 2

        # The method register_channel(channel) activates
        # that data from the respective channels is transferred
        # from the Time Tagger to the PC.
        self.register_channel(channel=self.click_channel)
        self.register_channel(channel=self.start_channel)
        self.register_channel(channel=self.start_channel_2)

        self.clear_impl()

        # At the end of a CustomMeasurement construction,
        # we must indicate that we have finished.
        self.finalize_init()

    def __del__(self):
        # The measurement must be stopped before deconstruction to avoid
        # concurrent process() calls.
        self.stop()

    def getData(self):
        # Acquire a lock this instance to guarantee that process() is not running in parallel
        # This ensures to return a consistent data.
        with self.mutex:
            return self.v_slope.copy()

    def getIndex(self):
        # This method does not depend on the internal state, so there is no
        # need for a lock.
        arr = np.arange(0, self.max_bins) * self.binwidth
        return arr

    def clear_impl(self):
        # The lock is already acquired within the backend.
        self.last_start_timestamp = 0
        self.data = np.zeros((self.max_bins,), dtype=np.uint64)
        self.v_slope = 0

    def on_start(self):
        # The lock is already acquired within the backend.
        pass

    def on_stop(self):
        # The lock is already acquired within the backend.
        pass

    @staticmethod
    @numba.jit(nopython=True, nogil=True)
    def fast_process(
            tags,
            data,
            v_slope,
            click_channel,
            start_channel,
            start_channel_2,
            binwidth,
            last_start_timestamp):
        """
        A precompiled version of the histogram algorithm for better performance
        nopython=True: Only a subset of the python syntax is supported.
                       Avoid everything but primitives and numpy arrays.
                       All slow operation will yield an exception
        nogil=True:    This method will release the global interpreter lock. So
                       this method can run in parallel with other python code
        """
        for tag in tags:
            # tag.type can be: 0 - TimeTag, 1- Error, 2 - OverflowBegin, 3 -
            # OverflowEnd, 4 - MissedEvents (you can use the TimeTagger.TagType IntEnum)
            if tag['type'] != TimeTagger.TagType.TimeTag:
                # tag is not a TimeTag, so we are in an error state, e.g. overflow
                last_start_timestamp = 0
            elif tag['channel'] == click_channel and last_start_timestamp != 0:
                # valid event
                index = (tag['time'] - last_start_timestamp) // binwidth
                if index < data.shape[0]:
                    data[index] += 1
            elif tag['channel'] == start_channel:
                last_start_timestamp = tag['time']
                v_slope = v_slope + (data[1] - data[0])/(data[1] - data[0])
            elif tag['channel'] == start_channel_2:
                last_start_timestamp = tag['time']

        return last_start_timestamp, v_slope

    def process(self, incoming_tags, begin_time, end_time):
        """
        Main processing method for the incoming raw time-tags.

        The lock is already acquired within the backend.
        self.data is provided as reference, so it must not be accessed
        anywhere else without locking the mutex.

        Parameters
        ----------
        incoming_tags
            The incoming raw time tag stream provided as a read-only reference.
            The storage will be deallocated after this call, so you must not store a reference to
            this object. Make a copy instead.
            Please note that the time tag stream of all channels is passed to the process method,
            not only the ones from register_channel(...).
        begin_time
            Begin timestamp of the of the current data block.
        end_time
            End timestamp of the of the current data block.
        """
        self.last_start_timestamp, self.v_slope = VisibilitySlope.fast_process(
            incoming_tags,
            self.data,
            self.v_slope,
            self.click_channel,
            self.start_channel,
            self.start_channel_2,
            self.binwidth,
            self.last_start_timestamp)
