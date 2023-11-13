# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control R&S SGS100A microwave device.

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

Parts of this file were developed from a PI3diamond module which is
Copyright (C) 2009 Helmut Rathgen <helmut.rathgen@gmail.com>

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import visa
import time
import numpy as np

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge


class Keithley2400(Base):
    """ Hardware file to control a R&S SGS100A microwave device.

    Example config for copy-paste:

    mw_source_sgs:
        module.Class: 'microwave.mw_source_sgs.MicrowaveSgs'
        gpib_address: 'GPIB0::12::INSTR'
        gpib_timeout: 10

    """

    # visa address of the hardware : this can be over ethernet, the name is here for
    # backward compatibility
    _address = ConfigOption('gpib_address', missing='error')
    _timeout = ConfigOption('gpib_timeout', 10, missing='warn')

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        self._timeout = self._timeout * 1000
        # trying to load the visa connection to the module
        self.rm = visa.ResourceManager()
        try:
            self._connection = self.rm.open_resource(self._address,
                                                          timeout=self._timeout)
        except:
            self.log.error('Could not connect to the address >>{}<<.'.format(self._address))
            raise

        self.model = self._connection.query('*IDN?').split(',')[1]
        self.log.info('Current source {} initialised and connected.'.format(self.model))
        # self._command_wait('*CLS')
        # self._command_wait('*RST')
        # self._command_wait(':LOCK? 72349234')
        return

    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        self.rm.close()
        return
    
    def on(self):
        
        self._connection.write('OUTP ON')
        self._connection.write('*WAI')

        return 0
    
    def off(self):
        
        self._connection.write('OUTP OFF')
        self._connection.write('*WAI')

        return 0

    def read_src_voltage(self):
        
        src_voltage = self._connection.query(':SOUR:VOLT?')
        self._connection.write('*WAI')

        return src_voltage

    def read_src_current(self):
        
        src_current = self._connection.query(':SOUR:CURR?')
        self._connection.write('*WAI')

        return src_current
    
    def read_measurement(self):
        
        measurement = self._connection.query(':READ?')
        self._connection.write('*WAI')

        return measurement
 
