# -*- coding: utf-8 -*-
"""
Interface file for pulsed lasers where current and power can be set.

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

import pyvisa as visa
import time
import numpy as np

from pycobolt import CoboltLaser, Cobolt06MLD

from core.module import Base
from core.configoption import ConfigOption
from interface.pulsed_laser_interface import SimpleLaserInterface
from interface.pulsed_laser_interface import ShutterState
from interface.pulsed_laser_interface import LaserState
from interface.pulsed_laser_interface import LaserMode
from interface.pulsed_laser_interface import ModulationType

class LaserFaults(Enum):
            NONE = 0
            TEMPERATURE = 1
            INTERLOCK = 2
            TIMEOUT = 3

class CoboltMLD06(Base, PulsedLaserInterface):
    """ Qudi module to communicate with the Cobolt MLD-06 Laser.

    Example config for copy-paste:

    cobolt_mld06:
        module.Class: 'laser.cobolt_mld06_laser.CoboltMLD06'
        port=None, serialnumber=None, baudrate=115200
        port: 'COM1'
        serial: 3333333
        baudrate: 115200
    """
        # Address configuration for laser
        _port = ConfigOption('port', 'COM1', missing='warn')
        _serial = ConfigOption('serialnumber', 333333, missing='warn')
        _baudrate = ConfigOption('baudrate', 115200, missing='warn')

    def on_activate(self):
        """ Activate module.
        """
        self.laser = Cobolt06MLD(_port, _serial)
        try:
            self.laser.connect()
        except:
            self.log.error('Could not connect to the serial number {}'.format(self._serial))
            raise

        self.log.info('Cobolt Laser {} initialized and connected.'.format(self._serial))
        return

    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        self.laser.disconnect()
        return

    def get_status(self):
        """ Gets the current status of the laser, i.e. the mode (const_current, const_power, modulation) and
            the output state (output on, output off)

        @return str, bool: mode [constant_current, constant_power, modulation], output on [True, False]
        """
        pass

    def get_power_range(self, mode):
        """ Return laser power
        @return tuple(p1, p2): Laser power range in watts
        """
        pass

    def get_power(self):
        """ Return laser power
        @return float power: Actual max laser power in watts for currently active mode
        """
        pass

    def set_power(self, power):
        """ Set laer power ins watts
          @param float power: max laser power setpoint in watts

          @return float: max laser power setpoint in watts
        """
        pass

    def get_power_setpoint(self):
        """ Return laser power setpoint
        @return float: Laser power setpoint in watts
        """
        pass

    def get_current_unit(self):
        """ Return laser current unit
        @return str: unit
        """
        pass

    def get_current(self):
        """ Return laser current
        @return float: actual laser current as ampere or percentage of maximum current
        """
        pass

    def get_current_range(self):
        """ Return laser current range
        @return tuple(c1, c2): Laser current range in current units
        """
        pass

    def get_current_setpoint(self):
        """ Return laser current
        @return float: Laser current setpoint in amperes
        """
        pass

    def set_current(self, current):
        """ Set laser current
        @param float current: Laser current setpoint in amperes
        @return float: Laser current setpoint in amperes
        """
        pass

    def allowed_control_modes(self):
        """ Get available control mode of laser
          @return list: list with enum control modes
        """
        pass

    def get_control_mode(self):
        """ Get control mode of laser
          @return enum ControlMode: control mode
        """
        pass

    def set_control_mode(self, control_mode):
        """ Set laser control mode.
          @param enum control_mode: desired control mode
          @return enum ControlMode: actual control mode
        """
        pass

    def on(self):
        """ Turn on laser. Does not open shutter if one is present.
          @return enum LaserState: actual laser state
        """
        pass

    def off(self):
        """ Turn off laser. Does not close shutter if one is present.
          @return enum LaserState: actual laser state
        """
        pass

    def get_laser_state(self):
        """ Get laser state.
          @return enum LaserState: laser state
        """
        pass

    def set_laser_state(self, state):
        """ Set laser state.
          @param enum state: desired laser state
          @return enum LaserState: actual laser state
        """
        pass

    def get_shutter_state(self):
        """ Get shutter state. Has a state for no shutter present.
          @return enum ShutterState: actual shutter state
        """
        return ShutterState.NOSHUTTER

    def set_shutter_state(self, state):
        """ Set shutter state.
          @param enum state: desired shutter state
          @return enum ShutterState: actual shutter state
        """
        pass

    def get_temperatures(self):
        """ Get all available temperatures from laser.
          @return dict: dict of name, value for temperatures
        """
        pass

    def get_temperature_setpoints(self):
        """ Get all available temperature setpoints from laser.
          @return dict: dict of name, value for temperature setpoints
        """
        pass

    def set_temperatures(self, temps):
        """ Set laser temperatures.
          @param temps: dict of name, value to be set
          @return dict: dict of name, value of temperatures that were set
        """
        pass

    def get_extra_info(self):
        """ Show dianostic information about lasers.
          @return str: diagnostic info as a string
        """
        pass
