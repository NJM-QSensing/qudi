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
from qtpy.QtWidgets import QMessageBox
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
        #self._qafm_logic.sigQAFMScanFinished.connect(self.enable_scan_actions)

        self._mw.actionStart_NVscan.triggered.connect(self.start_NVscan_clicked)

    def on_deactivate(self):
        self._mw.close()
        return 0     
    
    def show(self):
        """Make window visible and put it above all other windows. """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()

    def initMainUI(self):
        """ Definition, configuration and initialisation of the confocal GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        Moreover it sets default values.
        """
        self._mw = NVSCANMainWindow()
        #self._decorate_spectrum_plot()
        self._create_dockwidgets()
        self._create_NVConfocal_widgets()
        self._mw.centralwidget.hide()
        self._initialize_inputs()
        
    def show(self):
        """Make window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()  

    def _initialize_inputs(self):
        
        # set constraints
        self._mw.X_length_DSpinBox.setRange(0.0, 37e-6)
        self._mw.X_length_DSpinBox.setSuffix('m')
        self._mw.X_length_DSpinBox.setMinimalStep(0.1e-6)
        self._mw.X_length_DSpinBox.setValue(2e-6)

        self._mw.Y_length_DSpinBox.setRange(0.0, 37e-6)
        self._mw.Y_length_DSpinBox.setSuffix('m')
        self._mw.Y_length_DSpinBox.setMinimalStep(0.1e-6)
        self._mw.Y_length_DSpinBox.setValue(2e-6)


    
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
        experiment_list = self._NVscan_logic.NVConfocal_experiments_parameters()
        for experiment in experiment_list:
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
            sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                               QtWidgets.QSizePolicy.Expanding)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(0)
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
        experiments_meas = self._NVscan_logic.NVConfocal_experiments_meas_units()
        exp_unit_dict = experiments_meas[experiment_name]
        exp_text = list(exp_unit_dict.keys())         
        self._NV_spectrum_container[experiment_name] = pg.PlotDataItem(
                                    
                                    pen=pg.mkPen(palette.c1, style=QtCore.Qt.DotLine),
                                    symbol='o',
                                    symbolPen=palette.c1,
                                    symbolBrush=palette.c1,
                                    symbolSize=7)
        self._dockwidget_container[experiment_name].graphicsView.addItem(self._NV_spectrum_container[experiment_name])
        self._dockwidget_container[experiment_name].graphicsView.setLabel(axis='left', text= exp_text[0], units=exp_unit_dict[exp_text[0]])
        self._dockwidget_container[experiment_name].graphicsView.setLabel(axis='bottom', text= exp_text[1], units=exp_unit_dict[exp_text[1]])
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

        # create a grid layout
        grid = QtWidgets.QGridLayout(content)
        parent.gridLayout = grid
        parent.gridLayout.setObjectName("gridLayout")

        # arrange on grid
        grid.addWidget(graphicsView, 0, 0, 2, 6)

        parent_dock.GroupBox = GroupBox = QtWidgets.QGroupBox('Parameters')
        # create Size Policy for the widget.
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, 
                                           QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(parent_dock.sizePolicy().hasHeightForWidth())
        GroupBox.setSizePolicy(sizePolicy)

        # add each experiments' parameters and spin box
        GroupBox.setAlignment(QtCore.Qt.AlignLeft)
        gridLayout_groupBox = QtWidgets.QGridLayout(GroupBox)
        for key in experiment_dict[experiments_name]:
            label  = QtWidgets.QLabel(GroupBox)
            label.setText(key)
            experiment_parameter_units = experiment_dict[experiments_name][key]
            if float in experiment_parameter_units:
                SciDbox = ScienDSpinBox(GroupBox)
                SciDbox.setSuffix(experiment_parameter_units[0])
            elif int in experiment_parameter_units:
                Scibox = ScienSpinBox(GroupBox)
                Scibox.setSuffix(experiment_parameter_units[0])
            #setattr(parent_dock, f'label_{key}',label) 
            #setattr(parent_dock, f'doubleSpinBox_{experiment_dict[experiments_name][key]}',SciDbox)
            row_pos = list(experiment_dict[experiments_name]).index(key)
            gridLayout_groupBox.addWidget(label, row_pos+3, 1, 1, 1)
            gridLayout_groupBox.addWidget(SciDbox, row_pos+3, 2, 1, 1)
        
        grid.addWidget(GroupBox, 2, 0, 6, 6)

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

    def start_NVscan_clicked(self):
        #self.disable_scan_actions_quanti()

        X_length = self._mw.X_length_DSpinBox.value()
        Y_length = self._mw.Y_length_DSpinBox.value()
        X_pixels = self._mw.X_pixels_SpinBox.value()
        Y_pixels = self._mw.Y_pixels_SpinBox.value()

        self._NVscan_logic.start_ODMR_scan(
            coord_X_length=X_length, coord_Y_length=Y_length, coord_X_num=X_pixels, 
            coord_Y_num=Y_pixels)
