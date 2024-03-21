# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware module for AWG5000 Series.

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
from qcodes.instrument_drivers.tektronix.AWG5014 import Tektronix_AWG5014  
from qcodes.instrument import find_or_create_instrument
from core.util.modules import get_home_dir
import time
from ftplib import FTP
from socket import socket, AF_INET, SOCK_STREAM
import os
from collections import OrderedDict
from fnmatch import fnmatch
import re

from core.module import Base
from core.configoption import ConfigOption
from interface.pulser_interface import PulserInterface, PulserConstraints, SequenceOption


class AWG5014C(Base):
    """ A hardware module for the Tektronix AWG5000 series for generating
        waveforms and sequences thereof.

    Unstable and in construction, Alexander Stark

    Example config for copy-paste:

    pulser_awg5000:
        module.Class: 'awg.tektronix_awg5002c.AWG5002C'
        awg_ip_address: '10.42.0.211'
        awg_port: 3000 # the port number as integer
        timeout: 20
        # tmp_work_dir: 'C:\\Software\\qudi_pulsed_files' # optional
        # ftp_root_dir: 'C:\\inetpub\\ftproot' # optional, root directory on AWG device
        # ftp_login: 'anonymous' # optional, the username for ftp login
        # ftp_passwd: 'anonymous@' # optional, the password for ftp login
        # default_sample_rate: 600.0e6 # optional, the default sampling rate
    """

    # config options
    ip_address = ConfigOption('awg_ip_address', missing='error')



    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.connected = False

        self._marker_byte_dict = {0: b'\x00', 1: b'\x01', 2: b'\x02', 3: b'\x03'}
        self.current_loaded_asset = ''

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        config = self.getConfiguration()
        address = f'TCPIP0::{self.ip_address}::inst0::INSTR'
        self.awg1 = find_or_create_instrument(Tektronix_AWG5014, 'AWG1', address, timeout=40)


    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self.connected = False

   
