# -*- coding: utf-8 -*-

"""
This file contains the Qudi Predefined Measurements for MeasurementLogic

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

from abc import ABCMeta, abstractmethod
from qtpy import QtCore
import numpy as np
import copy

from core.util.helpers import natural_sort

from enum import Enum
from collections import OrderedDict

from logic.pulsed.pulse_extractor import PulseExtractor
from logic.pulsed.pulse_analyzer import PulseAnalyzer

class MeasurementSeries(object):
    """
    Collection of Measurments which is called a Measurement Series.

    Based off of PulseBlock()
    """

    def __init__(self, name, name_list=None):
        """
        The constructor for a Pulse_Block needs to have:

        @param str name: chosen name for the Pulse_Block
        @param list name_list: which contains the Pulse_Block_Element Objects forming a
                                  Pulse_Block, e.g. [Pulse_Block_Element, Pulse_Block_Element, ...]
        """
        self.name = name
        self.name_list = list() if name_list is None else name_list

        meas_dict = OrderedDict()
        self.shared_variables = OrderedDict()
        return

    def __repr__(self):
        repr_str = 'MeasurementSeries(name=\'{0}\', name_list=['.format(self.name)
        repr_str += ', '.join((repr(elem) for elem in self.name_list)) + '])'
        return repr_str

    def __str__(self):
        return_str = 'MeasurementSeries "{0}"\n\tnumber of elements: {1}\n\t'.format(
            self.name, len(self.name_list))
        return return_str

    def __len__(self):
        return len(self.name_list)

    def __getitem__(self, key):
        if not isinstance(key, (slice, int)):
            raise TypeError('MeasurementSeries indices must be int or slice, not {0}'.format(type(key)))
        return self.name_list[key]

    def __setitem__(self, key, value):
        if isinstance(key, int):
            if not isinstance(value, Measurement):
                raise TypeError('Measurement list entries must be of type Measurement,'
                                ' not {0}'.format(type(value)))

            self.name_list.append(value.name) 
        elif isinstance(key, slice):
            for element in value:
                if not isinstance(element, Measurement):
                    raise TypeError('Measurement list entries must be of type '
                                    'Measurement, not {0}'.format(type(value)))

        else:
            raise TypeError('MeasurementSeries indices must be int or slice, not {0}'.format(type(key)))
        self.name_list[key] = copy.deepcopy(value)
        return

    def __delitem__(self, key):
        if not isinstance(key, (slice, int)):
            raise TypeError('MeasurementSeries indices must be int or slice, not {0}'.format(type(key)))

        del self.name_list[key]

        return

    def __eq__(self, other):
        if not isinstance(other, MeasurementSeries):
            return False
        if self is other:
            return True
        for i, element in enumerate(self.name_list):
            if element != other[i]:
                return False
        return True

    def __iter__(self):
        self.measurement_index = 1
        return self

    def __next__(self):
        self.measurement_index += 1
        return self.measurement_index

    def __prev__(self):
        if self.measurement_index > 1:
            self.measurement_index -= 1
        
        return self.measurement_index

    def pop(self, position=None):
        if len(self.name_list) == 0:
            raise IndexError('pop from empty MeasurementSeries')

        if position is None:
            return self.name_list.pop()

        if not isinstance(position, int):
            raise TypeError('MeasurementSeries.pop position argument expects integer, not {0}'
                            ''.format(type(position)))

        if position < 0:
            position = len(self.name_list) + position

        if len(self.name_list) <= position or position < 0:
            raise IndexError('MeasurementSeries element list index out of range')

        return self.name_list.pop(position)

    def insert(self, position, element):
        """ Insert a MeasurementSeriesElement at the given position. The old element at this position and
        all consecutive elements after that will be shifted to higher indices.

        @param int position: position in the element list
        @param MeasurementSeriesElement element: MeasurementSeriesElement instance
        """
        if not isinstance(element, Measurement):
            raise ValueError('MeasurementSeries elements must be of type Measurement, not {0}'
                             ''.format(type(element)))

        if position < 0:
            position = len(self.name_list) + position

        if len(self.name_list) < position or position < 0:
            raise IndexError('MeasurementSeries element list index out of range')

        self.name_list.insert(position, copy.deepcopy(element))
        return

    def append(self, element):
        """
        """
        self.insert(position=len(self.name_list), element=element)
        return

    def extend(self, iterable):
        for element in iterable:
            self.append(element=element)
        return

    def clear(self):
        del self.name_list[:]
        return

    def reverse(self):
        self.name_list.reverse()
        return

    def get_dict_representation(self):
        dict_repr = dict()
        dict_repr['name'] = self.name
        dict_repr['name_list'] = list()
        for element in self.name_list:
            dict_repr['name_list'].append(element.get_dict_representation())
        return dict_repr

##########################################################################
#  Measurement classes
#
##########################################################################

class Measurement(metaclass=ABCMeta):
    """ This class represents a generalized NV measurement.
        To instantiate a new subclass, a user is expected to overload
        all abstract methods given in this abstract class.
    """
    # Measurement timer
    __timer_interval = 5

    # PulseExtractor settings
    extraction_parameters = None

    # PulseAnalysis settings
    analysis_parameters = None

    # Microwave Settings
    # TODO: Guarantee this is dict of dict, where the number of sources is 
    microwave_parameters = OrderedDict()

    # Counter Settings
    counter_parameters = OrderedDict()

    # Pulse Generator Settings
    pulser_parameters = OrderedDict()

    # General Data Type settings
    _data_units = None
    _controlled_variable = None
    _number_of_curves = None

    def __init__(self, name, sequencegeneratorlogic, measurementlogic, fitlogic):
        """ Initialize class
        """
        self.name = name
        self.__sequencegeneratorlogic = sequencegeneratorlogic
        self.__measurementlogic = measurementlogic
        self.__fitlogic = fitlogic

        self._pulseextractor = PulseExtractor(self.__measurementlogic)
        self._pulseanalyzer = PulseAnalyzer(self.__measurementlogic)

        self.fit_result = None

        # Measurement data
        self.signal_data = np.zeros([], dtype=float)
        self.signal_alt_data = np.zeros([], dtype=float)
        self.measurement_error = np.zeros([], dtype=float)
        self.laser_data = np.zeros([], dtype='int64')

        # Paused measurement flag
        self.__is_paused = False
        self._time_of_pause = None
        self._elapsed_pause = 0

        # For Fitting
        # Note: the fit container is made in either Confocal of Widefield Subclasses
        self.fit_result = None
        self.alt_fit_result = None
        self.signal_fit_data = np.zeros([], dtype=float)  # The x,y data of the fit result
        self.signal_fit_alt_data = np.zeros([], dtype=float)

    def __repr__(self):
        repr_str = 'Measurement(name=\'{0}\')'.format(self.name)
        return repr_str

    def __str__(self):
        repr_str = 'Measurement(name=\'{0}\')'.format(self.name)
        return repr_str

    def __eq__(self,other):
        """ Returns bool depending on whether this class
            is equal to another class instance
        """
        if not isinstance(other, Measurement):
            return False
        if self is other:
            return True
        
        return True

    ##########################################################################
    #  Sequence Generator Logic Properties
    #
    ##########################################################################

    @property
    def analyze_block_ensemble(self):
        return self.__sequencegeneratorlogic.analyze_block_ensemble

    @property
    def analyze_sequence(self):
        return self.__sequencegeneratorlogic.analyze_sequence

    @property
    def pulse_generator_settings(self):
        return self.__sequencegeneratorlogic.pulse_generator_settings

    @property
    def save_block(self):
        return self.__sequencegeneratorlogic.save_block

    @property
    def save_ensemble(self):
        return self.__sequencegeneratorlogic.save_ensemble

    @property
    def save_sequence(self):
        return self.__sequencegeneratorlogic.save_sequence

    @property
    def generation_parameters(self):
        return self.__sequencegeneratorlogic.generation_parameters

    @property
    def pulse_generator_constraints(self):
        return self.__sequencegeneratorlogic.pulse_generator_constraints

    @property
    def channel_set(self):
        channels = self.pulse_generator_settings.get('activation_config')
        if channels is None:
            channels = ('', set())
        return channels[1]

    @property
    def analog_channels(self):
        return {chnl for chnl in self.channel_set if chnl.startswith('a')}

    @property
    def digital_channels(self):
        return {chnl for chnl in self.channel_set if chnl.startswith('d')}

    @property
    def laser_channel(self):
        return self.generation_parameters.get('laser_channel')

    @property
    def sync_channel(self):
        channel = self.generation_parameters.get('sync_channel')
        return None if channel == '' else channel

    @property
    def gate_channel(self):
        channel = self.generation_parameters.get('gate_channel')
        return None if channel == '' else channel

    @property
    def analog_trigger_voltage(self):
        return self.generation_parameters.get('analog_trigger_voltage')

    @property
    def laser_delay(self):
        return self.generation_parameters.get('laser_delay')

    @property
    def microwave_channel(self):
        channel = self.generation_parameters.get('microwave_channel')
        return None if channel == '' else channel

    @property
    def microwave_frequency(self):
        return self.generation_parameters.get('microwave_frequency')

    @property
    def microwave_amplitude(self):
        return self.generation_parameters.get('microwave_amplitude')

    @property
    def laser_length(self):
        return self.generation_parameters.get('laser_length')

    @property
    def wait_time(self):
        return self.generation_parameters.get('wait_time')

    @property
    def rabi_period(self):
        return self.generation_parameters.get('rabi_period')

    @property
    def sample_rate(self):
        return self.pulse_generator_settings.get('sample_rate')


    ##########################################################################
    #  Measurement Logic Properties
    #
    ##########################################################################

    @property
    def is_gated(self):
        return self.__pulsedmeasurementlogic.counter_settings.get('is_gated')

    @property
    def measurement_settings(self):
        return self.__pulsedmeasurementlogic.measurement_settings

    @property
    def sampling_information(self):
        return self.__pulsedmeasurementlogic.sampling_information

    @property
    def counter_settings(self):
        return self.__pulsedmeasurementlogic.counter_settings

    @property
    def log(self):
        return self.__pulsedmeasurementlogic.log

class Confocal(Measurement):
    """ Measurement taking one set of data at once, as in a confocal NV microscope.
        This type of measurment cant be used for confocal microscopy experiments, 
        and scanning probe experiments.
    """

    def __init__(self, name):
        """ Initialize class
        """
        super().__init__(name)
        self.fit_container = self.__fitlogic.make_fit_container('{}_fc'.format(self.name), '1d')
        
class Widefield(Measurement):
    """ Measurement taking one many sets of data at once, as in a wide NV microscope.
        The methods in this method explicitely expect many pixels worth of data.
    """

    def __init__(self, name):
        """ Initialize class
        """
        super().__init__(name)
        self.fit_container = self.__fitlogic.make_fit_container('{}_fc'.format(self.name), '2d')


