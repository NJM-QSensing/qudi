# -*- coding: utf-8 -*-
"""
This file contains the Qudi GUI module for ODMR control.

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

from markdown import extensions
from math import log10, floor
from matplotlib import cm
import numpy as np
import pyqtgraph as pg
import os
import markdown
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy.QtWidgets import QMessageBox, QPushButton, QHBoxLayout
from qtpy import uic
from pyqtgraph import PlotWidget
import functools 

from core.module import Connector, StatusVar
from core.configoption import ConfigOption
from qtwidgets.scan_plotwidget import ScanPlotWidget
from qtwidgets.scientific_spinbox import ScienDSpinBox, ScienSpinBox
from qtwidgets.scan_plotwidget import ScanImageItem
from gui.guiutils import ColorBar
from gui.colordefs import QudiPalettePale as palette
from gui.color_schemes.color_schemes import ColorScaleGen

from gui.guibase import GUIBase

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

"""
Implementation Steps/TODOs:
- add default saveview as a file, which should be saved in the gui.
- check the colorbar implementation for smaller values => 32bit problem, quite hard...
"""

class NVSCANMainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'NVscan_gui.ui')

        # Load it
        super(NVSCANMainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()

class SequenceCreator(QtWidgets.QMainWindow):
    """ The settings dialog for ODMR measurements.
    """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'NVscan_sequence_creator.ui')

        # Load it
        super(SequenceCreator, self).__init__()
        uic.loadUi(ui_file, self)

class ConfigurationEditor(QtWidgets.QMainWindow):
    """ The settings dialog for editing measurements configuration.
    """
    def __init__(self):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'NVscan_configuration_editor.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)

class CustomCheckBox(QtWidgets.QCheckBox):

    # with the current state and the name of the box
    valueChanged_custom = QtCore.Signal(bool, str)

    def __init__(self, parent=None):

        super(CustomCheckBox, self).__init__(parent)
        self.stateChanged.connect(self.emit_value_name)

    @QtCore.Slot(int)
    def emit_value_name(self, state):
        self.valueChanged_custom.emit(bool(state), self.objectName())

class NVscanGui(GUIBase):

    ## declare connectors
    NVscanlogic = Connector(interface='NVscanlogic') # interface='NVscanlogic'

    _config_color_map = ConfigOption('color_map')  # user specification in config file

    _image_container = {}
    _NV_spectrum_container = {}
    _cb_container = {}
    _checkbox_container = {}
    _plot_container = {}
    _dockwidget_container = {}
    _experiments_group_order = []

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
    
    def on_activate(self):
        """ Definition and initialization of the GUI. """
        self._NVscan_logic = self.NVscanlogic()

        if self._config_color_map is not None:
            self._color_map = self._config_color_map

        self._current_cs = ColorScaleGen('seismic')        
        self.initMainUI()      # initialize the main GUI

        self._NVscan_logic.sigODMRpointScanFinished.connect(self._update_qafm_data)
        self._NVscan_logic.sigODMRpointScanFinished.connect(self._update_NVSpectrum_plots)
        #self.sigStartNVconfocal.connect(self._NVscan_logic.start_NVconfocal, QtCore.Qt.QueuedConnection)
        #self.sigStartNVconfocal.connect(self._NVscan_logic.start_NVconfocal, QtCore.Qt.QueuedConnection)


        self._mw.actionStart_NVscan.triggered.connect(self.start_NVscan_clicked)
        self._mw.action_Open_sequence_creator.triggered.connect(self._sequence_creator_settings)
        self._mw.action_Open_configuration.triggered.connect(self._configuration_editor_setting)

        #Connect NV confocal experiments buttons
        self._mw.PushButton_start_ODMR.clicked.connect(lambda:self.start_NV_confocal_measurement_clicked('ODMR'))
        self._mw.PushButton_stop_ODMR.clicked.connect(lambda:self.stop_NV_confocal_measurement_clicked('ODMR'))
        self._mw.PushButton_start_Rabi.clicked.connect(lambda:self.start_NV_confocal_measurement_clicked('Rabi'))
        self._mw.PushButton_stop_Rabi.clicked.connect(lambda:self.stop_NV_confocal_measurement_clicked('Rabi'))
        self._mw.PushButton_start_T1.clicked.connect(lambda:self.start_NV_confocal_measurement_clicked('T1'))
        self._mw.PushButton_stop_T1.clicked.connect(lambda:self.stop_NV_confocal_measurement_clicked('T1'))


    def on_deactivate(self):
        self._mw.close()
        self._sc.close()
        self._ce.close()
        return 0     
    
    

    def initMainUI(self):
        """ Definition, configuration and initialisation of the confocal GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        Moreover it sets default values.
        """
        self._mw = NVSCANMainWindow()
        self._sc = SequenceCreator()
        self._ce = ConfigurationEditor()
        #self._decorate_spectrum_plot()
        self._create_dockwidgets()
        self._create_NVConfocal_widgets()
        self._mw.centralwidget.hide()
        self._initialize_inputs()
        self._create_combobox_details()
        
    def show(self):
        """Make window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()  
    
    def _sequence_creator_settings(self):
        """ Open the settings menu """
        self._sc.show()

    def _configuration_editor_setting(self):
        self._ce.show()

    def _initialize_inputs(self):
        
        # AFM setting
        self._mw.X_length_DSpinBox.setRange(0.0, 37e-6)
        self._mw.X_length_DSpinBox.setSuffix('m')
        self._mw.X_length_DSpinBox.setMinimalStep(0.1e-6)
        self._mw.X_length_DSpinBox.setValue(2e-6)

        self._mw.Y_length_DSpinBox.setRange(0.0, 37e-6)
        self._mw.Y_length_DSpinBox.setSuffix('m')
        self._mw.Y_length_DSpinBox.setMinimalStep(0.1e-6)
        self._mw.Y_length_DSpinBox.setValue(2e-6)

        ## configuration setting
        self._ce.laser_time_DSpinBox.setSuffix('s')
        self._ce.laser_time_DSpinBox.setMinimalStep(1e-9)
        self._ce.laser_time_DSpinBox.setValue(1.5e-6)

        self._ce.wait_time_DSpinBox.setSuffix('s')
        self._ce.wait_time_DSpinBox.setMinimalStep(1e-9)
        self._ce.wait_time_DSpinBox.setValue(400e-9)

        self._ce.bin_width_DSpinBox.setSuffix('s')
        self._ce.bin_width_DSpinBox.setMinimalStep(1e-9)
        self._ce.bin_width_DSpinBox.setValue(1e-9)

        self._ce.microwave_modulation_frequency_DSpinBox.setSuffix('Hz')
        self._ce.microwave_modulation_frequency_DSpinBox.setMinimalStep(1e6)
        self._ce.microwave_modulation_frequency_DSpinBox.setValue(20e6)

        self._ce.microwave_modulation_frequency_DSpinBox.setSuffix('Hz')
        self._ce.microwave_modulation_frequency_DSpinBox.setMinimalStep(1e6)
        self._ce.microwave_modulation_frequency_DSpinBox.setRange(0.0, 20e6)
        self._ce.microwave_modulation_frequency_DSpinBox.setValue(20e6)

        self._ce.analyze_window_start_DSpinBox.setSuffix('s')
        self._ce.analyze_window_start_DSpinBox.setMinimalStep(self._ce.bin_width_DSpinBox.value())
        self._ce.analyze_window_start_DSpinBox.setRange(0, self._ce.laser_time_DSpinBox.value())
        self._ce.analyze_window_start_DSpinBox.setValue(0)

        self._ce.analyze_window_length_DSpinBox.setSuffix('s')
        self._ce.analyze_window_length_DSpinBox.setMinimalStep(self._ce.bin_width_DSpinBox.value())
        self._ce.analyze_window_length_DSpinBox.setRange(self._ce.analyze_window_start_DSpinBox.value(), self._ce.laser_time_DSpinBox.value())
        self._ce.analyze_window_length_DSpinBox.setValue(self._ce.laser_time_DSpinBox.value())


    
    # ========================================================================== 
    #         BEGIN: Creation and Adaptation of Display Widget
    # ========================================================================== 

    def _create_dockwidgets(self):
        """ Generate all the required DockWidgets. 

        To understand the creation procedure of the Display Widgets, it is 
        instructive to consider the file 'simple_dockwidget_example.ui'. The file 
        'simple_dockwidget_example.py' is the translated python file of the ui 
        file. The translation can be repeated with the pyui5 tool (usually an 
        *.exe or a *.bat file in the 'Scripts' folder of your python distribution)
        by running
              pyui5.exe simple_dockwidget_example.ui > simple_dockwidget_example.py
        From the 'simple_dockwidget_example.py' you will get the understanding
        how to create the dockwidget and its internal widgets in a correct way 
        (i.e. how to connect all of them properly together).
        The idea of the following methods are based on this creating process.

        The hierarchy looks like this

        DockWidget
            DockWidgetContent
                GraphicsView_1 (for main data)
                GraphicsView_2 (for colorbar)
                QDoubleSpinBox_1 (for minimal abs value)
                QDoubleSpinBox_2 (for minimal percentile)
                QDoubleSpinBox_3 (for maximal abs value)
                QDoubleSpinBox_4 (for maximal percentile)
                QRadioButton_1 (to choose abs value)
                QRadioButton_2 (to choose percentile)
                QCheckBox_1 (to set tilt correction)
              
        DockWidgetContent is a usual QWidget, hosting the internal content of the 
        DockWidget.

        Another good reference:
          https://www.geeksforgeeks.org/pyqt5-qdockwidget-setting-multiple-widgets-inside-it/

        """
        ref_last_dockwidget = None
        skip_colorcontrol = False
        c_scale = self._current_cs

        #connect all dock widgets to the central widget
        dockwidget = QtWidgets.QDockWidget(self._mw.centralwidget)  
        self._dockwidget_container['B_ext'] = dockwidget
        setattr(self._mw,  f'dockWidget_B_ext', dockwidget)
        dockwidget.name = 'B_ext'
        self._create_internal_widgets(dockwidget, skip_colorcontrol)
        dockwidget.setWindowTitle('B_ext')
        dockwidget.setObjectName(f'dockWidget_B_ext')
        
        #set size policy for dock widget
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                            QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(dockwidget.sizePolicy().hasHeightForWidth())
        dockwidget.setSizePolicy(sizePolicy)

        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(2), dockwidget)
        
        image_item = self._create_image_item('B_ext', np.zeros([10,10]))
        dockwidget.graphicsView_matrix.addItem(image_item)
        image_item.setLookupTable(c_scale.lut)

        colorbar = self._create_colorbar('B_ext', self._current_cs)
        dockwidget.graphicsView_cb.addItem(colorbar)
        dockwidget.graphicsView_cb.hideAxis('bottom')
        
        ref_last_dockwidget = dockwidget
        
        dockwidget = QtWidgets.QDockWidget(self._mw.centralwidget)  
        setattr(self._mw,  f'dockWidget_C_ext', dockwidget)
        dockwidget.name = 'C_ext'
        self._create_internal_widgets(dockwidget, skip_colorcontrol)
        dockwidget.setWindowTitle('C_ext')
        dockwidget.setObjectName(f'dockWidget_C_ext')
        
        #set size policy for dock widget
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                            QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(dockwidget.sizePolicy().hasHeightForWidth())
        dockwidget.setSizePolicy(sizePolicy)
        self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(2), dockwidget)
        colorbar = self._create_colorbar('B_ext', self._current_cs)
        dockwidget.graphicsView_cb.addItem(colorbar)
        dockwidget.graphicsView_cb.hideAxis('bottom')
        self._mw.tabifyDockWidget(ref_last_dockwidget, dockwidget)

    def _create_NVConfocal_widgets(self):
        ref_last_dockwidget = None
        is_first = True
        experiment_dict = self._NVscan_logic.NVConfocal_experiments_parameters()
        for experiment in experiment_dict:
            #connect all dock widgets to the central widget
            dockwidget = QtWidgets.QDockWidget(self._mw.centralwidget)  
            self._dockwidget_container[experiment] = dockwidget
            setattr(self._mw,  f'dockWidget_{experiment}', dockwidget)
            dockwidget.name = experiment     
            self._create_internal_line_widgets(experiment,dockwidget)
            self._decorate_NVspectrum_plotwidget(experiment)
            #self._create_internal_group_box(dockwidget)
            dockwidget.setWindowTitle(experiment)
            dockwidget.setObjectName(f'dockWidget_{experiment}')
            
            # set size policy for dock widget
            sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                               QtWidgets.QSizePolicy.Maximum)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(30)
            sizePolicy.setHeightForWidth(dockwidget.sizePolicy().hasHeightForWidth())
            dockwidget.setSizePolicy(sizePolicy)
            dockwidget.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea)
            if is_first:
                self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1), dockwidget)
                # QtCore.Qt.Orientation(2): vertical orientation
                self._mw.splitDockWidget(self._mw.LeftDock_1, dockwidget,
                                        QtCore.Qt.Orientation(2))
                is_first = False
            else:
                self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(1), dockwidget)              
                self._mw.tabifyDockWidget(ref_last_dockwidget, dockwidget)
            
            ref_last_dockwidget = dockwidget


    def _create_image_item(self, name, data_matrix):
        """ Helper method to create an Image Item.

        @param str name: the name of the image object
        @param np.array data_matrix: the data matrix for the image

        @return: ScanImageItem object
        """

        # store for convenience all the colorbars in a container
        self._image_container[name] = ScanImageItem(image=data_matrix, 
                                                    axisOrder='row-major')
        return self._image_container[name]

    def _decorate_NVspectrum_plotwidget(self,experiment):
        experiment_name = experiment
        experiment_name_2nd = experiment+'_2nd'
        experiment_name_3rd = experiment+'_3rd'
        experiment_name_4th = experiment+'_4th'
        experiment_name_5th = experiment+'_5th'
        experiment_name_6th = experiment+'_6th'
        experiments_meas = self._NVscan_logic.NVConfocal_experiments_measurements()
        exp_meas_y_name = experiments_meas[experiment_name][0][0]
        exp_meas_y_unit = experiments_meas[experiment_name][0][1]
        exp_meas_x_name = experiments_meas[experiment_name][1][0]
        exp_meas_x_unit = experiments_meas[experiment_name][1][1]     
        self._NV_spectrum_container[experiment_name] = pg.PlotDataItem(
                                    
                                    pen=pg.mkPen(palette.c4, style=QtCore.Qt.DotLine),
                                    symbol='o',
                                    symbolPen=palette.c4,
                                    symbolBrush=palette.c4,
                                    symbolSize=7)
        self._NV_spectrum_container[experiment_name_2nd] = pg.PlotDataItem(
                            
                            pen=pg.mkPen(palette.c3, style=QtCore.Qt.DotLine),
                            symbol='o',
                            symbolPen=palette.c3,
                            symbolBrush=palette.c3,
                            symbolSize=7)
        self._NV_spectrum_container[experiment_name_3rd] = pg.PlotDataItem(
                            
                            pen=pg.mkPen(palette.c2, style=QtCore.Qt.DotLine),
                            symbol='o',
                            symbolPen=palette.c2,
                            symbolBrush=palette.c2,
                            symbolSize=7)
        self._NV_spectrum_container[experiment_name_4th] = pg.PlotDataItem(
                            
                            pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                            symbol='o',
                            symbolPen=palette.c1,
                            symbolBrush=palette.c1,
                            symbolSize=7)
        self._NV_spectrum_container[experiment_name_5th] = pg.PlotDataItem(
                            
                            pen=pg.mkPen(palette.c5, style=QtCore.Qt.DotLine),
                            symbol='o',
                            symbolPen=palette.c5,
                            symbolBrush=palette.c5,
                            symbolSize=7)
        self._NV_spectrum_container[experiment_name_6th] = pg.PlotDataItem(
                            
                            pen=pg.mkPen(palette.c6, style=QtCore.Qt.DotLine),
                            symbol='o',
                            symbolPen=palette.c6,
                            symbolBrush=palette.c6,
                            symbolSize=7)

        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name])
        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name_2nd])
        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name_3rd])
        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name_4th])
        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name_5th])
        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name_6th])
        self._dockwidget_container[experiment_name].graphicsView.setLabel(axis='left', text=exp_meas_y_name, units=exp_meas_y_unit)
        self._dockwidget_container[experiment_name].graphicsView.setLabel(axis='bottom', text=exp_meas_x_name, units=exp_meas_x_unit)
        self._dockwidget_container[experiment_name].graphicsView.showGrid(x=True, y=True, alpha=0.8)
            
    def _create_colorbar(self, name, colorscale):
        """ Helper method to create Colorbar. 
        @param str name: the name of the colorbar object
        @param ColorScale colorscale: contains definition for colormap (colormap), 
                                  normalized colormap (cmap_normed) and Look Up 
                                  Table (lut).

        @return: Colorbar object
        """

        # store for convenience all the colorbars in a container
        self._cb_container[name] = ColorBar(colorscale.cmap_normed, width=100, 
                                            cb_min=0, cb_max=100)

        return self._cb_container[name]    
    
    def _create_internal_widgets(self, parent_dock, skip_colorcontrol=False):
        """  Create all the internal widgets for the dockwidget.

        @params parent_dock: the reference to the parent dock widget, which will
                             host the internal widgets
        """
        parent = parent_dock 

        # Create a Content Widget to which a layout can be attached.
        # add the content widget to the dockwidget
        content = QtWidgets.QWidget(parent)
        parent.dockWidgetContent = content
        parent.dockWidgetContent.setObjectName("dockWidgetContent")
        parent.setWidget(content)

        # create at first all required widgets

        parent_dock.graphicsView_matrix = graphicsView_matrix = ScanPlotWidget(content)
        graphicsView_matrix.setObjectName("graphicsView_matrix")

        parent.doubleSpinBox_cb_max = doubleSpinBox_cb_max = ScienDSpinBox(content)
        doubleSpinBox_cb_max.setObjectName("doubleSpinBox_cb_max")
        doubleSpinBox_cb_max.setMinimum(-100e9)
        doubleSpinBox_cb_max.setMaximum(100e9)

        parent_dock.doubleSpinBox_per_max = doubleSpinBox_per_max = ScienDSpinBox(content)
        doubleSpinBox_per_max.setObjectName("doubleSpinBox_per_max")
        doubleSpinBox_per_max.setMinimum(0)
        doubleSpinBox_per_max.setMaximum(100)
        doubleSpinBox_per_max.setValue(100.0)
        doubleSpinBox_per_max.setSuffix('%')

        parent_dock.graphicsView_cb = graphicsView_cb = ScanPlotWidget(content)
        graphicsView_cb.setObjectName("graphicsView_cb")

        parent_dock.doubleSpinBox_per_min = doubleSpinBox_per_min = ScienDSpinBox(content)
        doubleSpinBox_per_min.setObjectName("doubleSpinBox_per_min")
        doubleSpinBox_per_min.setMinimum(0)
        doubleSpinBox_per_min.setMaximum(100)
        doubleSpinBox_per_min.setValue(0.0)
        doubleSpinBox_per_min.setSuffix('%')
        doubleSpinBox_per_min.setMinimalStep(0.05)

        parent_dock.doubleSpinBox_cb_min = doubleSpinBox_cb_min = ScienDSpinBox(content)
        doubleSpinBox_cb_min.setObjectName("doubleSpinBox_cb_min")
        doubleSpinBox_cb_min.setMinimum(-100e9)
        doubleSpinBox_cb_min.setMaximum(100e9)

        parent.radioButton_cb_man = radioButton_cb_man = QtWidgets.QRadioButton(content)
        radioButton_cb_man.setObjectName("radioButton_cb_man")
        radioButton_cb_man.setText('Manual')
        parent_dock.radioButton_cb_per = radioButton_cb_per = QtWidgets.QRadioButton(content)
        radioButton_cb_per.setObjectName("radioButton_cb_per")
        radioButton_cb_per.setText('Percentiles')
        radioButton_cb_per.setChecked(True)
        parent.checkBox_tilt_corr = checkBox_tilt_corr = CustomCheckBox(content)
        checkBox_tilt_corr.setObjectName("checkBox_tilt_corr")
        checkBox_tilt_corr.setText("Tilt correction")
        checkBox_tilt_corr.setVisible(False)   # this will only be enabled for Heights

        # create required functions to react on change of the Radiobuttons:
        def cb_per_update(value):
            radioButton_cb_per.setChecked(True)
            self.sigColorBarChanged.emit(parent_dock.name)

        def cb_man_update(value):
            radioButton_cb_man.setChecked(True)
            self.sigColorBarChanged.emit(parent_dock.name)

        def tilt_corr_update(value):
            self.sigColorBarChanged.emit(parent_dock.name)

        parent_dock.cb_per_update = cb_per_update
        doubleSpinBox_per_min.valueChanged.connect(cb_per_update)
        doubleSpinBox_per_max.valueChanged.connect(cb_per_update)
        parent_dock.cb_man_update = cb_man_update
        doubleSpinBox_cb_min.valueChanged.connect(cb_man_update)
        doubleSpinBox_cb_max.valueChanged.connect(cb_man_update)
        parent_dock.tilt_corr_update = tilt_corr_update 
        checkBox_tilt_corr.valueChanged_custom.connect(tilt_corr_update)

        # create SizePolicy for only one spinbox, all the other spin boxes will
        # follow this size policy if not specified otherwise.
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, 
                                           QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(doubleSpinBox_cb_max.sizePolicy().hasHeightForWidth())
        doubleSpinBox_cb_max.setSizePolicy(sizePolicy)
        doubleSpinBox_cb_max.setMaximumSize(QtCore.QSize(100, 16777215))

        # create Size Policy for the colorbar. Let it extend in vertical direction.
        # Horizontal direction will be limited by the spinbox above.
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, 
                                           QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(graphicsView_cb.sizePolicy().hasHeightForWidth())
        graphicsView_cb.setSizePolicy(sizePolicy)
        graphicsView_cb.setMinimumSize(QtCore.QSize(80, 150))
        graphicsView_cb.setMaximumSize(QtCore.QSize(80, 16777215))

        # create a grid layout
        grid = QtWidgets.QGridLayout(content)
        parent.gridLayout = grid
        parent.gridLayout.setObjectName("gridLayout")

        # finally, arrange widgets on grid:
        # there are in total 7 rows, count runs from top to button, from left to
        # right.
        # it is (widget, fromRow, fromColum, rowSpan, columnSpan)
        if skip_colorcontrol:
            grid.addWidget(graphicsView_matrix,   0, 0, 1, 1) # start [0,0], span 7 rows down, 1 column wide
            doubleSpinBox_cb_max.hide()
            doubleSpinBox_per_max.hide()
            grid.addWidget(graphicsView_cb,       0, 1, 1, 1) # start [2,1], span 1 rows down, 1 column wide
            doubleSpinBox_per_min.hide()
            doubleSpinBox_cb_min.hide()
            radioButton_cb_man.hide()
            radioButton_cb_per.hide()
            checkBox_tilt_corr.hide()
        else:

            grid.addWidget(graphicsView_matrix,   0, 0, 7, 1) # start [0,0], span 7 rows down, 1 column wide
            grid.addWidget(doubleSpinBox_cb_max,  0, 1, 1, 1) # start [0,1], span 1 rows down, 1 column wide
            grid.addWidget(doubleSpinBox_per_max, 1, 1, 1, 1) # start [1,1], span 1 rows down, 1 column wide
            grid.addWidget(graphicsView_cb,       2, 1, 1, 1) # start [2,1], span 1 rows down, 1 column wide
            grid.addWidget(doubleSpinBox_per_min, 3, 1, 1, 1) # start [3,1], span 1 rows down, 1 column wide
            grid.addWidget(doubleSpinBox_cb_min,  4, 1, 1, 1) # start [4,1], span 1 rows down, 1 column wide
            grid.addWidget(radioButton_cb_man,    5, 1, 1, 1) # start [5,1], span 1 rows down, 1 column wide
            grid.addWidget(radioButton_cb_per,    6, 1, 1, 1) # start [6,1], span 1 rows down, 1 column wide
            grid.addWidget(checkBox_tilt_corr,    7, 0, 1, 1) # start [7,0], span 1 rows down, 1 column wide

    def _create_internal_line_widgets(self, experiment, parent_dock):

        parent = parent_dock
        experiments_name = experiment
        experiment_dict = self._NVscan_logic.NVConfocal_experiments_parameters()

        # Create a Content Widget to which a layout can be attached.
        # add the content widget to the dockwidget
        content = QtWidgets.QWidget(parent)
        parent.dockWidgetContent = content
        parent.dockWidgetContent.setObjectName("dockWidgetContent")
        parent.setWidget(content)

        # create the only widget
        parent_dock.graphicsView = graphicsView = PlotWidget(content)
        setattr(self._mw, f'line_plot_{experiments_name}',graphicsView) 
        graphicsView.setObjectName(experiments_name)

        # create Size Policy for the widget.
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, 
                                           QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(graphicsView.sizePolicy().hasHeightForWidth())
        graphicsView.setSizePolicy(sizePolicy)
        
        parent_dock.GrouScrollAreapBox = ScrollArea = QtWidgets.QScrollArea(content)
        ScrollArea.setWidgetResizable(True)
        ScrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        ScrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # create Size Policy for the widget.
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, 
                                           QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(parent_dock.sizePolicy().hasHeightForWidth())
        ScrollArea.setSizePolicy(sizePolicy)

        # add each experiments' parameters and spin box
        ScrollArea.setAlignment(QtCore.Qt.AlignLeft)
        gridLayout_ScrollArea = QtWidgets.QGridLayout(ScrollArea)
        
        for i,para in enumerate(experiment_dict[experiments_name]):
            label  = QtWidgets.QLabel(ScrollArea)
            para_name = para[0]
            para_unit = para[1]
            para_type = para[2]
            label.setText(para_name)
            if para_type == float:
                Scibox = ScienDSpinBox(ScrollArea)
                Scibox.setSuffix(para_unit)
                setattr(self._mw, f'DSpinBox_{experiments_name}_{para_name}',Scibox)

            elif para_type == int:
                Scibox = ScienSpinBox(ScrollArea)
                Scibox.setSuffix(para_unit)
                setattr(self._mw, f'SpinBox_{experiments_name}_{para_name}',Scibox)
            label.setSizePolicy(sizePolicy)
            Scibox.setSizePolicy(sizePolicy)

            gridLayout_ScrollArea.addWidget(label, i, 0, 1, 2)
            gridLayout_ScrollArea.addWidget(Scibox, i, 2, 1, 2)
        
        # create start and stop measurements butttons
        button_start = QtWidgets.QPushButton(f'start {experiments_name}')
        gridLayout_ScrollArea.addWidget(button_start, i+1, 0, 1, 2)
        button_stop = QtWidgets.QPushButton(f'stop {experiments_name}')
        gridLayout_ScrollArea.addWidget(button_stop, i+1, 2, 1, 2)
        setattr(self._mw, f'PushButton_start_{experiments_name}',button_start)
        setattr(self._mw, f'PushButton_stop_{experiments_name}',button_stop)

        
        # create a grid layout for linewidget and groupbox
        grid = QtWidgets.QGridLayout(content)
        parent.gridLayout = grid
        parent.gridLayout.setObjectName("gridLayout")        
        grid.addWidget(graphicsView, 0, 0, 10, 2)
        grid.addWidget(ScrollArea, 0, 2, 10, 1)
    
    def _create_combobox_details(self):
        self._mw.hBoxLayout = QHBoxLayout()
        self._mw.add_measurement_button = QPushButton("Add Measurement")
        self._mw.add_measurement_button.clicked.connect(self._on_clicked_add_measurement)
        self._mw.delete_last_measurement_button = QPushButton("Delete Measurement")
        self._mw.delete_last_measurement_button.clicked.connect(self.on_clicked_delete_last_measurement)
        self._mw.hBoxLayout.addWidget(self._mw.add_measurement_button)
        self._mw.hBoxLayout.addWidget(self._mw.delete_last_measurement_button)
        self._mw.verticalLayout.addLayout(self._mw.hBoxLayout)
        return 0

    def _on_clicked_add_measurement(self):
        #experiment_dict = self._NVscan_logic.NVConfocal_experiments_parameters()
        current_text = self._mw.comboBox.currentText()
        self._experiments_group_order.append(current_text)
        self._mw.listWidget.addItem(current_text)
    
    def on_clicked_delete_last_measurement(self):
        count = self._mw.listWidget.count()
        removed_item = self._mw.listWidget.takeItem(count-1)
        if removed_item != None:
            removed_text = removed_item.text()
            self._experiments_group_order.pop()
            print(removed_text)

    def _update_qafm_data(self):
        """ Update all displays of the qafm scan with data from the logic. """
        NVscan_data = self._NVscan_logic.get_qafm_data()
        cb_range = self._get_scan_cb_range('B_ext',data=NVscan_data)
        #if NVscan_data['B_ext']['display_range'] is not None:
        #    NVscan_data['B_ext']['display_range'] = cb_range 
        self._image_container['B_ext'].setImage(image=NVscan_data,
                                                levels=(cb_range[0], cb_range[1]))
        self._refresh_scan_colorbar('B_ext', data=NVscan_data)
        # self._image_container[obj_name].getViewBox().setAspectLocked(lock=True, ratio=1.0)
        self._image_container['B_ext'].getViewBox().updateAutoRange()
    
    def _update_NVSpectrum_plots(self):
        """ Refresh the plot widgets with new data. """
        # Update mean signal plot
        odmr_data_y = self._NVscan_logic.ODMR_spectrum_single
        odmr_data_x = self._NVscan_logic.ODMR_freq
        self._NV_spectrum_container['ODMR'].setData(odmr_data_x, odmr_data_y)


        
    def get_dockwidget(self, objectname):
        """ Get the reference to the dockwidget associated to the objectname.

        @param str objectname: name under which the dockwidget can be found.
        """

        dw = self._dockwidget_container.get(objectname)
        if dw is None:
            self.log.warning(f'No dockwidget with name "{objectname}" was found! Be careful!')

        return dw
    
    def _refresh_scan_colorbar(self, dockwidget_name, data=None):
        """ Update the colorbar of the Dockwidget.

        @param str dockwidget_name: the name of the dockwidget to update.
        """

        cb_range =  self._get_scan_cb_range(dockwidget_name,data=data)
        self._cb_container[dockwidget_name].refresh_colorbar(cb_range[0], cb_range[1])

    def _get_scan_cb_range(self, dockwidget_name,data=None):
        """ Determines the cb_min and cb_max values for the xy scan image.
        @param str dockwidget_name: name associated to the dockwidget.

        """
        
        dockwidget = self.get_dockwidget(dockwidget_name)

        if data is None:
            data = self._image_container[dockwidget_name].image

        # If "Manual" is checked, or the image data is empty (all zeros), then take manual cb range.
        if dockwidget.radioButton_cb_man.isChecked() or np.count_nonzero(data) < 1:
            cb_min = dockwidget.doubleSpinBox_cb_min.value()
            cb_max = dockwidget.doubleSpinBox_cb_max.value()

        # Otherwise, calculate cb range from percentiles.
        else:
            # Exclude any zeros (which are typically due to unfinished scan)
            data_nonzero = data[np.nonzero(data)]

            # Read centile range
            low_centile = dockwidget.doubleSpinBox_per_min.value()
            high_centile = dockwidget.doubleSpinBox_per_max.value()

            cb_min = np.percentile(data_nonzero, low_centile)
            cb_max = np.percentile(data_nonzero, high_centile)

        cb_range = [cb_min, cb_max]

        return cb_range

    
        
    
    def disable_buttons(self,name):
        target_experiment_button = name
        experiment_dict = self._NVscan_logic.NVConfocal_experiments_parameters()
        for experiments in experiment_dict:
            if target_experiment_button == experiments:
                start_button = getattr(self._mw, f'PushButton_start_{target_experiment_button}')
                start_button.setEnabled(False)
            else:
                start_button = getattr(self._mw, f'PushButton_start_{experiments}')
                stop_button = getattr(self._mw, f'PushButton_stop_{experiments}')
                start_button.setEnabled(False)
                stop_button.setEnabled(False)

    def enable_buttons(self,name):
        target_experiment_button = name
        experiment_dict = self._NVscan_logic.NVConfocal_experiments_parameters()
        for experiments in experiment_dict:
            if target_experiment_button == experiments:
                start_button = getattr(self._mw, f'PushButton_start_{target_experiment_button}')
                start_button.setEnabled(True)
            else:
                start_button = getattr(self._mw, f'PushButton_start_{experiments}')
                stop_button = getattr(self._mw, f'PushButton_stop_{experiments}')
                start_button.setEnabled(True)
                stop_button.setEnabled(True)

# ========================================================================== 
#          Measurement: Helper Function for  Measurement
# ========================================================================== 

    def start_NVscan_clicked(self):
        """ Triggered by the start_NVscan Button. Initiate the scanning sequence. This function will conduct each NV confocal experiement according to the _experiments_group_order list.
        """

        X_length = self._mw.X_length_DSpinBox.value()
        Y_length = self._mw.Y_length_DSpinBox.value()
        X_pixels = self._mw.X_pixels_SpinBox.value()
        Y_pixels = self._mw.Y_pixels_SpinBox.value()

        parameter_dict = self.get_NVconfocal_experiment_parameters(experiment_name)
        config_dict = self.get_NVconfocal_experiement_configuration()
        measurement_group = self.get_NVconfocal_experiment_configuration
        for i in range(len(measurement_group)):
            experiment_name = measurement_group[i]
            self.start_NV_confocal_scan(experiment_name, parameter_dict, config_dict)
        return 0

    def start_NV_confocal_scan(self, experiment_name, parameter_dict, config_dict):
        pass

    def start_NV_confocal_measurement_clicked(self,experiment_name):
        self.disable_buttons(experiment_name)
        exp_parameters_dict = self.get_NVconfocal_experiment_parameters(experiment_name)
        exp_config_dict = self.get_NVconfocal_experiment_configuration()
        self._NVscan_logic.start_NVconfocal(experiment_name, exp_parameters_dict, exp_config_dict, self)

    def stop_NV_confocal_measurement_clicked(self,name):
        experiment_name = name
        self.enable_buttons(experiment_name)
        #self._NVscan_logic.stop_NVconfocal()

    def get_NVconfocal_experiment_parameters(self, experiment_name):
        exp_parameters_dict = {}
        item_list = dir(self._mw)
        spinbox_list = [keys_name for keys_name in item_list if f'SpinBox_{experiment_name}' in keys_name]
        for spinbox_name in spinbox_list:
            if 'DSpinBox_' in spinbox_name:
                value_name = spinbox_name.replace('DSpinBox_', '')
            else:
                value_name = spinbox_name.replace('SpinBox_', '')
            exp_parameters_dict[value_name] = getattr(self._mw,spinbox_name).value()
            
        return exp_parameters_dict
    
    def get_NVconfocal_experiment_configuration(self):
        config_parameters_dict = {}
        item_list = dir(self._ce)
        spinbox_list = [keys_name for keys_name in item_list if 'SpinBox' in keys_name]
        for spinbox_name in spinbox_list:
            value_name = spinbox_name.replace('_DSpinBox', '')
            config_parameters_dict[value_name] = getattr(self._ce,spinbox_name).value()

        return config_parameters_dict