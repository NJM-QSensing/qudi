# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware module to use TimeTagger as a counter.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import TimeTagger as tt
import time
import numpy as np
from collections import namedtuple
from enum import Enum

from core.module import Base
from core.configoption import ConfigOption

from interface.counter_interface import CounterInterface

from interface.counter_interface import CounterInterface, CounterMode, CounterState

    
class TimeTaggerCounter(Base, CounterInterface):
    """ Using the TimeTagger as a counter (combined fast and slow).

    Example config for copy-paste:

    timetagger_slowcounter:
        module.Class: 'timetagger_counter.TimeTaggerCounter'
        timetagger_channel_apd_0: 0
        timetagger_channel_apd_1: 1
        timetagger_sum_channels: 2

    """

    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', None, missing='warn')
    _sum_channels = ConfigOption('timetagger_sum_channels', False)

    _channel_detect = ConfigOption('_channel_detect', 2, missing='error')
    _channel_next = ConfigOption('_channel_next', 3, missing='error')
    _channel_sync = ConfigOption('_channel_sync', 4, missing='warn')
    _channel_mw_next = ConfigOption('_channel_mw_next', 5, missing='warn')

    def on_activate(self):
        """ Start up TimeTagger interface
        """
        self._tagger = tt.createTimeTagger()
        self.config = tt.getConfiguration()
        self.counter = None

        self._settings = dict()
        self.mode = CounterMode.UNCONFIGURED

        if self._sum_channels and self._channel_apd_1 is None:
            self.log.error('Cannot sum channels when only one apd channel given')

        if self._sum_channels:
            self._channel_combined = tt.Combiner(self._tagger, channels=[self._channel_apd_0, self._channel_apd_1])
            self._channel_apd = self._channel_combined.getChannel()
        else:
            self._channel_apd = self._channel_apd_0

        self.log.info('TimeTagger (fast counter) configured to use  channel {0}'
                      .format(self._channel_apd))

        self.status = CounterState.IDLE

    def on_deactivate(self):
        """ Shut down the TimeTagger, stopping it from running if necessary.
        """
        if self.module_state() == 'locked' and self.status == CounterState.RUNNING:
            self.counter.stop()
        tt.freeTimeTagger(self._tagger)
        self.counter = None
        self.status = CounterState.IDLE
        self.mode = CounterMode.UNCONFIGURED

    def get_constraints(self):
        """ Get hardware limits the device

        @return SlowCounterConstraints: constraints class for slow counter

        FIXME: ask hardware for limits when module is loaded
        """
        constraints = dict()

        # the unit of those entries are seconds per bin. In order to get the
        # current binwidth in seonds use the get_binwidth method.
        constraints['hardware_binwidth_list'] = [0.1 / 1e9 ,1 / 1e9, 10/1e9, 100/1e9,400/1e9]

        constraints['min_count_frequency'] = 1e-3
        constraints['max_count_frequency'] = 10e9

        return constraints

    # ==========================================================================
    #                 SlowCounter Resembling Functions
    # ==========================================================================


    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """ Configures the hardware clock of the TimeTagger for timing

        @param float clock_frequency: if defined, this sets the frequency of
                                      the clock
        @param string clock_channel: if defined, this is the physical channel
                                     of the clock

        @return int: error code (0:OK, -1:error)
        """
        self._settings.clear()
        self._settings['clock_frequency'] = clock_frequency
        return 0

    def set_up_counter(self,
                       counter_channels=None,
                       sources=None,
                       clock_channel=None,
                       counter_buffer=None):
        """ Configures the actual counter with a given clock.

        @param str counter_channel: optional, physical channel of the counter
        @param str photon_source: optional, physical channel where the photons
                                  are to count from
        @param str counter_channel2: optional, physical channel of the counter 2
        @param str photon_source2: optional, second physical channel where the
                                   photons are to count from
        @param str clock_channel: optional, specifies the clock channel for the
                                  counter
        @param int counter_buffer: optional, a buffer of specified integer
                                   length, where in each bin the count numbers
                                   are saved.

        @return int: error code (0:OK, -1:error)
        """

        # currently, parameters passed to this function are ignored -- the channels used and clock frequency are
        # set at startup

        self.configure(CounterMode.COUNTER,
                       bin_width_s = (1/self.settings['clock_frequency']),
                       n_values = 1)

        self.mode = CounterMode.COUNTER

        self.log.info('Set up counter with {0}'.format(self.settings['clock_frequency']))
        return 0

    def get_counter_channels(self):
            return [self._channel_apd]

    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return numpy.array(uint32): the photon counts per second
        """
        if self.mode is not CounterMode.COUNTER:
            self.log.error("Timetagger not in Counter Mode")
            return -1

        counts = np.zeros(samples, dtype='uint32')
        for i in range(len(counts)):
            time.sleep(2 / self.settings['clock_frequency'])
            counts[i] = self.counter.getData() * self.settings['clock_frequency']

        return counts

    def close_counter(self):
        """ Closes the counter and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        self.counter.stop()
        self.status = CounterState.IDLE
        return 0

    def close_clock(self):
        """ Closes the clock and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    # ==========================================================================
    #                 FastCounter Resembling Functions
    # ==========================================================================

    def configure(self, mode, properties, **kwargs):

        """ Configuration of the counter.

        @param int measurement_mode: from CounterMode(Enum), which determines the type of CounterMode
        @param dict properties: dict containing properties to set up measurement mode
        @param kwargs: additional properties to set up measurement mode

        @return tuple(properties + kwargs): tuple contains list of properties which were actually set
        """

        if self.status != CounterState.UNCONFIGURED and self.status != CounterState.IDLE: 
            # on the fly configuration (in BUSY state) is only allowed in CW_MW mode.
            self.log.error(f'TimeTagger cannot be configured in the '
                           f'requested mode "{CounterMode.name(mode)}", since the device '
                           f'state is in "{self.status.name}". Stop ongoing '
                           f'measurements and make sure that the device is '
                           f'connected to be able to configure if '
                           f'properly.')
            return -1
        
        if isinstance(properties,dict):
            properties.update(kwargs)
        else:
            self.log.error("Properties must be a dict() to configure counter")

        if mode == CounterMode.TIMEDIFFERENCES:
            self.counter, settings = self.create_timedifferences(properties) 
        elif mode == CounterMode.COUNTBETWEENMARKERS:
            self.counter, settings = self.create_countbetweenmarkers(properties)
        elif mode == CounterMode.HISTOGRAM:
            self.counter, settings = self.create_histogram(properties)
        elif mode == CounterMode.COUNTER:
            self.counter, settings = self.create_counter(properties)
        elif mode == CounterMode.COUNTRATE:
            self.counter, settings = self.create_countrate(properties)
        else:
            self.log.error(f'Requested mode "{CounterMode.name(mode)}" not available.')
            return -1

        self.mode = mode

        return settings

    def start_measure(self):
        """ Start the counter. """
        self.module_state.lock()
        self.counter.clear()
        self.counter.start()
        self._tagger.sync()
        self.status = CounterState.RUNNING
        return 0

    def start_measure_For(self, duration, clear=True,timeout=-1):
        """ Start the counter for duration.
        """
        self.module_state.lock()
        self.counter.clear()
        self.counter.startFor(duration, clear)
        self._tagger.sync()
        self.counter.waitUntilFinished(timeout=timeout)
        self.module_state.unlock()
        return 0

    def stop_measure(self):
        """ Stop the counter. """
        if self.module_state() == 'locked':
            self.counter.stop()
            self.counter.clear()
            self.module_state.unlock()
        self.status = CounterState.IDLE
        return 0

    def is_running(self):
        """ Query if TT is currently taking data
        """
        if self.mode is CounterMode.UNCONFIGURED:
            return False
        return self.counter.isRunning()

    def pause_measure(self):
        """ Pauses the current measurement.

        Counter must be initially in the run state to make it pause.
        """
        if self.module_state() == 'locked':
            self.counter.stop()
            self.status = CounterState.PAUSED
        return 0

    def continue_measure(self):
        """ Continues the current measurement.

        If fast counter is in pause state, then fast counter will be continued.
        """
        if self.module_state() == 'locked':
            self.counter.start()
            self._tagger.sync()
            self.status = CounterState.RUNNING
        return 0

    def is_gated(self):
        """ Check the gated counting possibility.

        Boolean return value indicates if the fast counter is a gated counter
        (TRUE) or not (FALSE).
        """
        return True

    def get_data_trace(self):
        """ Polls the current timetrace data from the fast counter.

        @return numpy.array: 2 dimensional array of dtype = int64. This counter
                             is gated the the return array has the following
                             shape:
                                returnarray[gate_index, timebin_index]

        The binning, specified by calling configure() in forehand, must be taken
        care of in this hardware class. A possible overflow of the histogram
        bins must be caught here and taken care of.
        """
        info_dict = {'elapsed_sweeps': self.counter.getCounts(),
                     'elapsed_time': None}  
        return np.array(self.counter.getData(), dtype='int64'), info_dict


    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.status

    def get_binwidth(self):
        """ Returns the width of a single timebin in the timetrace in seconds. """
        if 'bin_width_s' in self._settings.keys():
            return self._settings['bin_width_s']
        else:
            self.log.info('Current Measurement has no bin_width')
            return

    # ==========================================================================
    #                 Helper Functions
    # ==========================================================================


    def create_timedifferences(self, settings):

        """ Configuration of the time differences .
        
        dict() containing:

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._settings.clear()

        required = {"bin_width_s" : None,
                    "record_length_s" : None}

        optional = {"number_of_gates": 0,
                    "use_sync": True,
                    "use_next": True}

        self.check_settings(required, optional, settings)

        bin_width_ps = int(self._settings['bin_width_s'] * 1e12)
        n_bins = int(self._settings['record_length_s']
                     / self._settings['bin_width_s'])

        if self._settings['use_sync']:
            sync_channel = self._channel_sync
        else:
            sync_channel = tt.CHANNEL_UNUSED

        if self._settings['use_next']:
            next_channel = self._channel_next
        else:
            next_channel = tt.CHANNEL_UNUSED        
       
        self.status = CounterState.IDLE
        self.counter = tt.TimeDifferences(
            tagger=self._tagger,
            click_channel=self._channel_apd,
            start_channel=self._channel_detect,
            next_channel=next_channel,
            sync_channel=sync_channel,
            binwidth=bin_width_ps,
            n_bins=n_bins,
            n_histograms=self._settings['number_of_gates'])

        self.counter.stop()
        self.counter.clear()

        return (self._settings['bin_width_s'],
                self._settings['record_length_s'],
                self._settings['number_of_gates'])

    def create_countbetweenmarkers(self, settings):

        """ Configuration of the time differences .
        
        dict() containing:

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._settings.clear()

        required = {"num_meas" : None}

        optional = {}

        self.check_settings(required, optional, settings)

        self.status = CounterState.IDLE
        self.counter = tt.CountBetweenMarkers(
            self._tagger,
            click_channel=self._channel_apd,
            begin_channel=self._channel_detect,
            end_channel=self._channel_next,
            n_values=self._settings['num_meas']
        )

        self.counter.stop()
        self.counter.clear()
        
        return self._settings['num_meas']

    def create_histogram(self, settings):

        """ Configuration of the time differences .
        
        dict() containing:

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._settings.clear()

        required = {"bin_width_s" : None,
                    "record_length_s" : None}

        optional = {}

        self.check_settings(required, optional, settings)
        
        bin_width_ps = int(self._settings['bin_width_s'] * 1e12)
        n_bins = int(self._settings['record_length_s']
                     / self._settings['bin_width_s'])      
       
        self.status = CounterState.IDLE
        self.counter = tt.Histogram(
            tagger=self._tagger,
            click_channel=self._channel_apd,
            start_channel=self._channel_detect,
            binwidth=bin_width_ps,
            n_bins=n_bins)

        self.counter.stop()
        self.counter.clear()

        return (self._settings['bin_width_s'],
                self._settings['record_length_s'])

    def create_counter(self, settings):

        """ Configuration of the time differences .
        
        dict() containing:

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._settings.clear()

        required = {"bin_width_s" : None,
                    "n_bins" : None}

        optional = {}

        self.check_settings(required, optional, settings)

        bin_width_ps = int(self._settings['bin_width_s'] * 1e12)
        n_bins = int(self._settings['n_bins'])      
       
        self.status = CounterState.IDLE
        self.counter = tt.Counter(
            tagger=self._tagger,
            channels=self._channel_apd,
            binwidth=bin_width_ps,
            n_bins=n_bins)

        self.counter.stop()
        self.counter.clear()

        return (self._settings['bin_width_s'],
                self._settings['n_bins'])

    def create_countrate(self, settings):

        """ Configuration of the time differences .
        
        dict() containing:

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._settings.clear()

        required = {}

        optional = {}

        self.check_settings(required, optional, settings)    
       
        self.status = CounterState.IDLE
        self.counter = tt.Countrate(
            tagger=self._tagger,
            channels=self._channel_apd)

        self.counter.stop()
        self.counter.clear()

        return

    def check_settings(self, required, optional, settings):
        """ Checks if configure() input is valid to create a measurement
        """
        for key in required:
            if key not in settings.keys():
                self.log.error("Required Property Missing in TimeDifferences")
                return
            self._settings[key] = settings[key]

        for key in optional.keys():
            if key in settings.keys():
                self._settings[key] = settings[key]
            else:
                self._settings[key] = optional[key]
        return        

    def get_measurements(self):
        """ Get measurements.

        It is the responsibility of whatever calls this function to format the data, depending
        on the current measurement mode.

        @return int_array: numpy array of measurement. Shape depends upon 
                           current mode setting
        """
        while True:
            if self.counter.ready():
                break

        return self.counter.getData()

    def setMaxCounts(self, max_counts):
        """ Set Max Counts.
        @param int

        @return int_array: numpy array of measurement. Shape depends upon 
                           current mode setting
        """
        if not isinstance(max_counts, int):
            self.log.warning('Max Counts was not an integer.')

        if self.status is CounterState.IDLE:
            self.counter.setMaxCounts(int(max_counts))

        return
