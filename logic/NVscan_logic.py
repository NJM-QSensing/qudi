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
import json
import TimeTagger

#from deprecation import deprecated

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
    pulser = Connector(interface='PulserInterface')
    fastcounter = Connector(interface='FastCounterInterface')

    sigODMRpointScanFinished = QtCore.Signal()
  
    def on_activate(self):
        # in this threadpool our worker thread will be run
        self.threadpool = QtCore.QThreadPool()
        self._pulser = self.pulser()
        self._microwave = self.microwave()
        self._fastcounter = self.fastcounter()
        self._seq_load_path = 'C:/Users/cduPC/Documents/GitHub/qudi/logic/NVscan_sequences/'
    
    def on_deactivate(self):
        pass         
    
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
    
    def start_NVconfocal(self, experiment_name, exp_parameters_dict, exp_config_dict, nvscan_gui):
        """This function initiate and manage the NVScan Measurement."""
        # First generate the Sequence for Pulse Streamer
        self.seq, self.meas_time = self.generate_pulsed_sequence(experiment_name, exp_parameters_dict, exp_config_dict)
        # Second Load the generated sequence into the Pulsed Streamer
        self.seq_block,self.measure_time = self.load_pulsed_sequence(self.seq, self.meas_time)
        # Third set up timetagger
        self.counter = self.set_timetagger(experiment_name, exp_parameters_dict, exp_config_dict)
        # Fourth construct update method
        self.update_func = self.set_update_func(experiment_name, exp_parameters_dict, exp_config_dict, nvscan_gui)
        # Finally Start Scanning
        self.initiate_scanning(experiment_name, exp_parameters_dict, exp_config_dict)
        pass
    
    def generate_pulsed_sequence(self, experiment_name, exp_parameters_dict, exp_config_dict):
        """This function generate the sequence for the Pulse Streamer"""
        function_dict = self.NVConfocal_experiments_function()[experiment_name]
        seq_block, meas_time = function_dict['sequence_generator'](experiment_name, exp_parameters_dict, exp_config_dict)
        return seq_block, meas_time

    def load_pulsed_sequence(self, sequence, meas_time):
        """This function load the sequence into the pulse streamer"""
        self._seq = self._pulser.pulse_streamer.createSequence()
            
        for i, key in enumerate(sequence):
            if key[0] == 'D':
                channel = int(key[1:])
                self._seq.setDigital(channel,sequence[key])
            elif key[0] == 'A':
                channel = int(key[1:])
                self._seq.setAnalog(channel,sequence[key])
        self._seq.setDigital(6,[(meas_time-100,0),(100,1)]) #sync


        return (sequence, meas_time)
    
    def set_timetagger(self, experiment_name, exp_parameters_dict, exp_config_dict):
        tagger = TimeTagger.createTimeTagger()
        binwidth_ps = 1e3
        n_bins = int(exp_config_dict['laser_time']/1e-9)
        num_points = exp_parameters_dict[experiment_name+'_num_points']
        counter = TimeTagger.TimeDifferences(tagger=tagger, click_channel=1, start_channel=2, next_channel=2,
            sync_channel=3,binwidth=binwidth_ps, n_bins=n_bins, n_histograms=num_points)
        return counter

    def set_update_func(self, experiment_name, exp_parameters_dict, exp_config_dict, nvscan_gui):
        analyze_window_start=int(exp_config_dict['analyze_window_start']/1e-9)
        analyze_window_length = int(exp_config_dict['analyze_window_length']/1e-9)
        prefix = experiment_name+'_'
        num_points = exp_parameters_dict[prefix+'num_points']
        start_length = exp_parameters_dict[prefix+'Start_length']
        step_size = exp_parameters_dict[prefix+'Step_length']
        mw_length = np.linspace(start_length,num_points*(step_size),num_points)
        self.timer = None
        def update_func():
            if self._pulser.pulse_streamer.hasFinished():
                self.timer.stop()
                self._microwave.off()
            counts_raw = self.counter.getData()
            counts = np.mean(counts_raw[:,analyze_window_start:analyze_window_start+analyze_window_length],1)
            nvscan_gui._NV_spectrum_container[experiment_name].setData(mw_length, counts)
        return update_func
    
    def initiate_scanning(self, experiment_name, exp_parameters_dict, exp_config_dict):
        self.timer = QtCore.QTimer(interval=200, timeout=self.update_func)
        self.timer.start()
        mw_freq = exp_parameters_dict[experiment_name+'_Frequency']
        mw_power = exp_parameters_dict[experiment_name+'_MW_power']
        self._microwave.set_frequency(mw_freq)
        self._microwave.cw_on()
        self._microwave.set_power(mw_power)
        integration_time = exp_parameters_dict[experiment_name+'_Integration_time'] #sec
        n_runs = int(integration_time*1e9/self.meas_time)
        self.counter.clear()
        time.sleep(0.1)
        self._pulser.pulse_streamer.stream(self._seq,n_runs)
        self._pulser.pulse_streamer.startNow()

    def setup_counter(self):
        # n_bins = laser_time
        # binwidth_s = 1e-9
        # number_of_gates = num_points
        self.fastcounter.configure(self, binwidth_s, n_bins, number_of_gates)

    # ========================================================================== 
    #          Helper Function
    # ========================================================================== 
    def add_block(self, on_off_state,state_time):
        seq_element = []
        for i,val in enumerate(state_time):
            seq_element.extend([(state_time[i],on_off_state[i])])
        return seq_element
    
    def load_dictionary(self, filename):
        with open(filename) as f:
            dic = json.loads(f.read())
        return dic

    def get_data(self, analyze_window_start, analyze_window_length):
        
        counts_raw = self._counterlogic.plused.getData()
        counts = np.mean(counts_raw[:,analyze_window_start:analyze_window_start+analyze_window_length],1)
        
        return counts
    
    def get_qafm_data(self):
        return self.B
    
    def save_sequence(self, address, sequence):

        return 0
    
    def on_off_extract(self, channel,seq_dict):
        on_off = []
        for val in seq_dict:
            if channel in seq_dict[val]:
                on_off.extend([1])
            else:
                on_off.extend([0])

            on_off.pop()
        return on_off
    
    # ========================================================================== 
    #          Configuration
    # ========================================================================== 
    def NVConfocal_experiments_function(self):
        experiments_function = {
                            'ODMR':         {'sequence_generator': self.ODMR_sequence_generator},
                            'Rabi':         {'sequence_generator': self.Rabi_sequence_generator},
                            'T1':           {'sequence_generator': self.T1_sequence_generator}
        }
        return experiments_function
    
    def NVConfocal_experiments_parameters(self):
        experiments_para = {'ODMR':        [
                                            ['Central_frequency', 'Hz', float],
                                            ['Frequency_range', 'Hz', float],
                                            ['Integration_time', 's', float],
                                            ['MW_power', 'dBm', float],
                                            ['num_points', '', int]
                                            ],
                             'Rabi':       [
                                            ['Frequency', 'Hz', float],
                                            ['Start_length', 's',float], 
                                            ['Step_length', 's', float],
                                            ['Integration_time', 's', float],
                                            ['MW_power', 'dBm', float],
                                            ['num_points', '', int]                                                                                        
                                            ],
                             'T1':         [
                                            ['Frequency', 'Hz', float],
                                            ['pi_pulse_length', 's',float],    
                                            ['Start_time', 's',float], 
                                            ['Stop_time', 's',float],
                                            ['Integration_time', 's', float],
                                            ['MW_power', 'dBm', float], 
                                            ['num_points', '', int]                                                                                       
                                            ]
                            }        
        return experiments_para
    
    def NVConfocal_experiments_measurements(self):
        experiments_measurements = {'ODMR':        [
                                                    ['PL', 'Counts'],
                                                    ['MW_frequency', 'Hz']    
                                                    ],
                                    'Rabi':        [
                                                    ['PL', 'Counts'],
                                                    ['MW_pulse_length', 's']     
                                                    ],
                                    'T1':          [
                                                    ['PL', 'Counts'],
                                                    ['Delay_time', 's']    
                                                    ]
                                    }        
        return experiments_measurements

    def ODMR_sequence_generator(self, experiment_name, exp_parameters_dict, exp_config_dict):
        # load sequence dict
        seq_dict = self.load_dictionary(self._seq_load_path + experiment_name + '.txt')

        # parameters
        prefix = experiment_name+'_'
        num_points = exp_parameters_dict[prefix+'num_points']
        mw_sweep_time = 1e6 #ns
        meas_time = 10e6 #ns

        # config
        
        seq_block = {}

        for channles in seq_dict['used channels']:
            seq_block[channles]=[]

        for i in range(num_points):
            state_time =[mw_sweep_time ,meas_time]
            for channel in seq_block:
                on_off_state = self.on_off_extract(channel,seq_dict)
                seq_block[channel].extend(self.add_block(on_off_state,state_time))         
                
            meas_time += np.sum(state_time)
        return seq_block, meas_time

    def Rabi_sequence_generator(self, experiment_name, exp_parameters_dict, exp_config_dict):
            

        # load sequence dict
        seq_dict = self.load_dictionary(self._seq_load_path + experiment_name + '.txt')
        # parameters
        prefix = experiment_name+'_'
        num_points = exp_parameters_dict[prefix+'num_points']
        step_size = exp_parameters_dict[prefix+'Step_length'] #ns
        start_length = exp_parameters_dict[prefix+'Start_length'] #ns
            
        # config
        laser_time = exp_config_dict['laser_time'] # 1.6e3 #ns
        wait_time = exp_config_dict['wait_time'] # 500 #ns
            
        meas_time = 0
        
        seq_block = {}
        
        for channles in seq_dict['used channels']:
            seq_block[channles]=[]

        for i in range(num_points):
            state_time =[(start_length+step_size*i)*1e9 ,laser_time*1e9 ,wait_time*1e9 ]
            for channel in seq_block:
                on_off_state = self.on_off_extract(channel,seq_dict)
                seq_block[channel].extend(self.add_block(on_off_state,state_time))         
                
            meas_time += np.sum(state_time)
        return seq_block, meas_time

    def T1_sequence_generator(self, experiment_name, exp_parameters_dict, exp_config_dict):
        meas_time = 0
        
        seq_block = {}

        return seq_block, meas_time
