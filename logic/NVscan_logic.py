# -*- coding: utf-8 -*-
"""
This file contains the Qudi logic <####>.

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


#from hardware.microwaveQ.microwaveq import MicrowaveQ    # for debugging only
#from hardware.spm.spm_new import SmartSPM                # for debugging only
from interface.scanner_interface import ScanStyle, ScannerMode
from hardware.timetagger_counter import HWRecorderMode
from core.module import Connector, StatusVar
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from core.util import units
from core.util.mutex import Mutex
from scipy.linalg import lstsq
from math import log10, floor
from scipy.stats import norm
from collections import deque
import threading
import numpy as np
import os
import re
import time
import datetime
import matplotlib.pyplot as plt
import math
from . import gwyfile as gwy

from deprecation import deprecated

from qtpy import QtCore

class WorkerThread(QtCore.QRunnable):
    """ Create a simple Worker Thread class, with a similar usage to a python
    Thread object. This Runnable Thread object is intented to be run from a
    QThreadpool.

    @param obj_reference target: A reference to a method, which will be executed
                                 with the given arguments and keyword arguments.
                                 Note, if no target function or method is passed
                                 then nothing will be executed in the run
                                 routine. This will serve as a dummy thread.
    @param tuple args: Arguments to make available to the run code, should be
                       passed in the form of a tuple
    @param dict kwargs: Keywords arguments to make available to the run code
                        should be passed in the form of a dict
    @param str name: optional, give the thread a name to identify it.
    """

    def __init__(self, target=None, args=(), kwargs={}, name=''):
        super(WorkerThread, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.target = target
        self.args = args
        self.kwargs = kwargs

        if name == '':
            name = str(self.get_thread_obj_id())

        self.name = name
        self._is_running = False

    def get_thread_obj_id(self):
        """ Get the ID from the current thread object. """

        return id(self)

    @QtCore.Slot()
    def run(self):
        """ Initialise the runner function with passed self.args, self.kwargs."""

        if self.target is None:
            return

        self._is_running = True
        self.target(*self.args, **self.kwargs)
        self._is_running = False

    def is_running(self):
        return self._is_running

    def autoDelete(self):
        """ Delete the thread. """
        self._is_running = False
        return super(WorkerThread, self).autoDelete()


class NVscanlogic(GenericLogic):
    """ Main AFM logic class providing advanced measurement control. """
    microwave = Connector(interface='MicrowaveInterface')
    
    sigODMRpointScanFinished = QtCore.Signal()
  
    def on_activate(self):
        # in this threadpool our worker thread will be run
        self.threadpool = QtCore.QThreadPool()
    def start_ODMR_scan(self,
            coord_X_length, coord_Y_length, coord_X_num, 
            coord_Y_num):
        self._worker_thread = WorkerThread(target=self.ODMR_scan,
                                               args=(coord_X_length, coord_Y_length, 
                                                     coord_X_num, coord_Y_num, 
                                                    ),
                                               name='qanti_thread')
        self.threadpool.start(self._worker_thread)


    def ODMR_scan(self,
            coord_X_length, coord_Y_length, coord_X_num, 
            coord_Y_num):
        # Create dumy data
        load_path = 'Z:/phys-cdu71/Du_Georgia Tech_GroupDrive/NV_LowTemp_Scanning/Samples_and_Data/twist_CrI3/device2/data/twist_area_odmr/1p8K/fine_area4'
        self.B_dummy = np.genfromtxt(load_path+'/20230221-0552-50_TestTag_1_autosave_QAFM_b_field_fw.dat')
        ODMR_spectrum_dummy = np.genfromtxt(load_path+'/20230221-0552-50_TestTag_1_autosave_esr_data_esr_fw.dat')
        self.ODMR_freq = np.linspace(2.65e9,2.95e9,30)
        self.ODMR_spectrum_single = np.zeros(30)
        self.B = np.zeros([100,150])
        ODMR_spectrum = np.zeros([15000,30])
        for j in range(coord_Y_num):
            for i in range(coord_X_num):
                self.B[j,i] = self.B_dummy[j,i]
                ODMR_spectrum[j*150+i,:] = ODMR_spectrum_dummy[j*150+i,:]
                self.ODMR_spectrum_single = ODMR_spectrum_dummy[j*150+i,:]
                time.sleep(0.05)
                self.sigODMRpointScanFinished.emit()
                #time.sleep(0.2)
                #self.log.info('pasa')
 

        return self.B
    
    def get_qafm_data(self):
        return self.B
    
  
    def NVConfocal_experiments_parameters(self):
        experiments_para = {'ODMR':        {'Central frequency' : ['Hz', float],
                                            'Frequency range': ['Hz', float],  
                                           },
                             'Rabi':       {'Frequency' : ['Hz', float],
                                              'pi pulse length': ['s',float],     
                                              'Start length': ['s',float], 
                                              'Step length': ['s',float]},
                             'T1':         {'Frequency' : ['Hz', float],
                                              'pi pulse length': ['s',float],    
                                              'Start time': ['s',float], 
                                              'Stop time': ['s',float]},
                            }        
        return experiments_para
    
    def NVConfocal_experiments_meas_units(self):
        meas_unit = {'ODMR':        {'PL' : 'Counts/s',
                                            'MW frequency': 'Hz',    
                                },
                   'Rabi':         {'PL' : 'Counts',
                                    'MW pulse length': 's',     
                                },
                   'T1':           {'PL' : 'Counts',
                                    'Delay time': 's',    
                                },
                     }        
        return meas_unit
        
 

 
