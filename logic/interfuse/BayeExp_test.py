# -*- coding: utf-8 -*-
"""
This file contains the Qudi Interfuse file for ODMRCounter and Pulser.

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
import numpy as np
from matplotlib import pyplot as plt
from time import sleep
import TimeTagger
from optbayesexpt import OptBayesExpt, MeasurementSimulator
import pyvisa as visa

##### MW source
# _address = 'TCPIP0::169.254.2.20::inst0::INSTR'
# _timeout = 20

# def on_activate(self):
#     """ Initialisation performed during activation of the module. """
#     self._timeout = self._timeout * 1000
#     # trying to load the visa connection to the module
#     self.rm = visa.ResourceManager()
#     try:
#         self._connection = self.rm.open_resource(self._address,
#                                                         timeout=self._timeout)
#     except:
#         self.log.error('Could not connect to the address >>{}<<.'.format(self._address))
#         raise

#     self.model = self._connection.query('*IDN?').split(',')[1]
#     self.log.info('MW {} initialised and connected.'.format(self.model))
#     print('MW {} initialised and connected.'.format(self.model))
#     # self._command_wait('*CLS')
#     # self._command_wait('*RST')
#     return

# on_activate()

# def off(self):
#     """
#     Switches off any microwave output.
#     Must return AFTER the device is actually stopped.

#     @return int: error code (0:OK, -1:error)
#     """
#     mode, is_running = self.get_status()
#     if not is_running:
#         return 0

#     self._connection.write('OUTP:STAT OFF')
#     self._connection.write('*WAI')
#     return 0

# def set_frequency(self, frequency=None):
#     """ Sets the microwave source in CW mode, and sets the MW power.
#     Method ignores whether the output is on or off

#     @param (float) frequency: frequency to set in Hz

#     @return int: error code (0:OK, -1:error)
#     """
#     mode, is_running = self.get_status()

#     # Activate CW mode
#     if mode != 'cw':
#         self._command_wait(':FREQ:MODE CW')

#     # Set CW frequency
#     if frequency is not None:
#         self._command_wait(':FREQ {0:f}'.format(frequency))

#     return 0

# def get_status(self):
#     """
#     Gets the current status of the MW source, i.e. the mode (cw, list or sweep) and
#     the output state (stopped, running)

#     @return str, bool: mode ['cw', 'list', 'sweep'], is_running [True, False]
#     """
#     is_running = bool(int(float(self._connection.query('OUTP:STAT?'))))
#     mode = self._connection.query(':FREQ:MODE?').strip('\n').lower()
#     if mode == 'swe':
#         mode = 'sweep'
#     return mode, is_running
# set_frequency(2e9)
#####
#Create a TimeTagger instance to control your hardware
tagger = TimeTagger.createTimeTagger()

# Create an instance of the Counter measurement class. It will start acquiring data immediately.
counter = TimeTagger.Counter(tagger=tagger, channels=[1], binwidth=int(1e9), n_values=10)

# Data is retrieved by calling the method "getData" on the measurement class.
duration = 1e12 
counter.startFor(duration)
data = counter.getData()
sleep(2)

data = np.array(data)
print("The Array is: ", data)
TimeTagger.freeTimeTagger(tagger)

# ########################################################################
# #           SETUP
# ########################################################################

# # Script tuning parameters
# ## Measurement loop: Quit measuring after ``n_measure`` measurement iterations
# n_measure = 500

# # random number generator
# try:
#     rng = np.random.default_rng()
# except:
#     rng = np.random

# # Tuning the OptBayesExpt behavior
# #
# # The parameter probability distribution is represented by ``n_samples``
# # samples from the distribution.
# n_samples = 50000
# # The parameter selection method is determined by ``optimal``.
# # optimal = True        # use OptBayesExpt.opt_setting()
# optimal = False  # use OptBayesExpt.good_setting() with pickiness
# pickiness = 19  # ignored when optimal == True


# # Describe how the world works with a model function
# #
# def my_model_function(sets, pars, cons):
#     """ Evaluates a trusted model of the experiment's output

#     The equivalent of a fit function. The argument structure is
#     required by OptBayesExpt. In this example, the model function is a
#     Lorentzian peak.

#     Args:
#         sets: A tuple of setting values, or a tuple of settings arrays
#         pars: A tuple of parameter arrays or a tuple of parameter values
#         cons: A tuple of floats

#     Returns:  the evaluated function
#     """
#     # unpack the settings
#     x, = sets
#     # unpack model parameters
#     x0, a, b = pars
#     # unpack model constants
#     d, = cons

#     # calculate the Lorentzian
#     return b + a / (((x - x0) / d) ** 2 + 1)


# # Define the allowed measurement settings
# #
# # 200 values between 1.5 and 4.5 (GHz)
# xvals = np.linspace(2.77, 2.87, 200)
# # sets, pars, cons are all expected to be tuples
# settings = (xvals,)

# # Define the prior probability distribution of the parameters
# #
# # resonance center x0 -- a flat prior around 3
# x0_min, x0_max = (2.77, 2.87)
# x0_samples = rng.uniform(x0_min, x0_max, n_samples)
# # amplitude parameter a -- flat prior
# a_samples = rng.uniform(-2000, -400, n_samples)
# # background parameter b -- a gaussian prior around 250000
# b_mean, b_sigma = (50000, 1000)
# b_samples = rng.normal(b_mean, b_sigma, n_samples)
# # Pack the parameters into a tuple.
# # Note that the order must correspond to how the values are unpacked in
# # the model_function.
# parameters = (x0_samples, a_samples, b_samples)
# param_labels = ['Center', 'Amplitude', 'Background']
# # Define Constants
# #
# dtrue = .1
# constants = (dtrue,)

# # make an instance of OptBayesExpt
# #
# my_obe = OptBayesExpt(my_model_function, settings, parameters, constants,
#                       scale=False)

# ########################################################################
# #           MEASUREMENT LOOP
# ########################################################################

# # arrays to collect the outputs
# xdata = np.zeros(n_measure)
# ydata = np.zeros(n_measure)
# sig = np.zeros((n_measure, 3))

# # Perform measurements
# for i in np.arange(n_measure):

#     # determine settings for the measurement
#     # OptBayesExpt does Bayesian experimental design
#     if optimal:
#         xmeas = my_obe.opt_setting()
#     else:
#         xmeas = my_obe.good_setting(pickiness=pickiness)

#     ## set frequency of MW

#     ymeasure = counter.startFor(duration)
#     xdata[i] = xmeas[0]
#     ydata[i] = ymeasure

#     # package the results
#     measurement = (xmeas, ymeasure)
#     # OptBayesExpt does Bayesian inference
#     my_obe.pdf_update(measurement)

#     # OptBayesExpt provides statistics to track progress
#     sigma = my_obe.std()
#     sig[i] = sigma

#     # entertainment
#     if i % 100 == 0:
#         print("{:3d}, sigma = {}".format(i, sigma[0]))


