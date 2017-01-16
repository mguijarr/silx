# coding: utf-8
# /*##########################################################################
#
# Copyright (c) 2017 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ###########################################################################*/
"""
This module  define model and widget to display 1D slices from numpy
array using compound data types or hdf5 databases.
"""
from __future__ import division

import itertools
import numbers
import numpy
import six
from silx.gui import qt

__authors__ = ["V. Valls"]
__license__ = "MIT"
__date__ = "16/01/2017"


class _MultiLineItem(qt.QItemDelegate):
    """Draw a multiline text without hiding anything.

    Default behaviour for multiline text is quite strange
    """

    def __init__(self, parent=None):
        """
        Constructor

        :param qt.QWidget parent: Parent of the widget
        """
        qt.QItemDelegate.__init__(self, parent)
        self.__textOptions = qt.QTextOption()
        self.__textOptions.setFlags(qt.QTextOption.IncludeTrailingSpaces |
                                    qt.QTextOption.ShowTabsAndSpaces)
        self.__textOptions.setWrapMode(qt.QTextOption.NoWrap)
        self.__textOptions.setAlignment(qt.Qt.AlignTop | qt.Qt.AlignLeft)

    def paint(self, painter, option, index):
        """
        Write multiline text without using any wrap or any alignment according
        to the cell size.
        """
        painter.save()

        # set colors
        painter.setPen(qt.QPen(qt.Qt.NoPen))
        if option.state & qt.QStyle.State_Selected:
            brush = option.palette.highlight()
            painter.setBrush(brush)
        else:
            brush = index.data(qt.Qt.BackgroundRole)
            if brush is None:
                # default background color for a cell
                brush = qt.Qt.white
            painter.setBrush(brush)
        painter.drawRect(option.rect)

        if index.isValid():
            if option.state & qt.QStyle.State_Selected:
                brush = option.palette.highlightedText()
            else:
                brush = index.data(qt.Qt.ForegroundRole)
                if brush is None:
                    brush = option.palette.text()
            painter.setPen(qt.QPen(brush.color()))
            text = index.data(qt.Qt.DisplayRole)
            painter.drawText(qt.QRectF(option.rect), text, self.__textOptions)

        painter.restore()


class RecordTableModel(qt.QAbstractTableModel):
    """This data model provides access to 1D slices from numpy array using
    compound data types or hdf5 databases.

    Each entries are displayed in a single row, and each columns contain a
    specific field of the compound type.

    It also allows to display 1D arrays of simple data types.
    array.

    :param qt.QObject parent: Parent object
    :param numpy.ndarray data: A numpy array or a h5py dataset
    """
    def __init__(self, parent=None, data=None):
        qt.QAbstractTableModel.__init__(self, parent)

        self.__format = "%g"
        self.__data = None
        self.__fields = None

        # set _data
        self.setArrayData(data)

    def toString(self, data):
        """Rendering a data into a readable string

        :param data: Data to render
        :rtype: str
        """
        if isinstance(data, (tuple, numpy.void)):
            text = [self.toString(d) for d in data]
            return "(" + " ".join(text) + ")"
        elif isinstance(data, (list, numpy.ndarray)):
            text = [self.toString(d) for d in data]
            return "[" + " ".join(text) + "]"
        elif isinstance(data, (numpy.string_, numpy.object_, bytes)):
            try:
                return "\"%s\"" % data.decode("utf-8")
            except UnicodeDecodeError:
                pass
            import binascii
            return binascii.hexlify(data).decode("ascii")
        elif isinstance(data, six.string_types):
            return "\"%s\"" % data
        elif isinstance(data, numpy.complex_):
            if data.imag < 0:
                template = self.__format + " - " + self.__format + "j"
            else:
                template = self.__format + " + " + self.__format + "j"
            return template % (data.real, data.imag)
        elif isinstance(data, numbers.Number):
            return self.__format % data
        return str(data)

    # Methods to be implemented to subclass QAbstractTableModel
    def rowCount(self, parent_idx=None):
        """Returns number of rows to be displayed in table"""
        if self.__data is None:
            return 0
        else:
            return len(self.__data)

    def columnCount(self, parent_idx=None):
        """Returns number of columns to be displayed in table"""
        if self.__fields is None:
            return 1
        else:
            return len(self.__fields)

    def data(self, index, role=qt.Qt.DisplayRole):
        """QAbstractTableModel method to access data values
        in the format ready to be displayed"""
        if not index.isValid():
            return None

        if self.__data is None:
            return None

        if index.row() >= len(self.__data):
            return None
        data = self.__data[index.row()]

        if self.__fields is not None:
            if index.column() >= len(self.__fields):
                return None
            key = self.__fields[index.column()][1]
            data = data[key[0]]
            if len(key) > 1:
                data = data[key[1]]

        if role == qt.Qt.DisplayRole:
            return self.toString(data)

    def headerData(self, section, orientation, role=qt.Qt.DisplayRole):
        """Returns the 0-based row or column index, for display in the
        horizontal and vertical headers"""
        if role == qt.Qt.DisplayRole:
            if orientation == qt.Qt.Vertical:
                return str(section)
            if orientation == qt.Qt.Horizontal:
                if self.__fields is None:
                    if section == 0:
                        return "Data"
                    else:
                        return None
                else:
                    if section < len(self.__fields):
                        return self.__fields[section][0]
                    else:
                        return None
        return None

    def flags(self, index):
        """QAbstractTableModel method to inform the view whether data
        is editable or not."""
        return qt.QAbstractTableModel.flags(self, index)

    def setArrayData(self, data):
        """Set the data array and the viewing perspective.

        You can set ``copy=False`` if you need more performances, when dealing
        with a large numpy array. In this case, a simple reference to the data
        is used to access the data, rather than a copy of the array.

        .. warning::

            Any change to the data model will affect your original data
            array, when using a reference rather than a copy..

        :param data: 1D numpy array, or any object that can be
            converted to a numpy array using ``numpy.array(data)`` (e.g.
            a nested sequence).
        """
        if qt.qVersion() > "4.6":
            self.beginResetModel()

        self.__data = data
        self.__fields = []
        if data is not None:
            if data.dtype.fields is not None:
                for name, (dtype, _index) in data.dtype.fields.items():
                    if dtype.shape != tuple():
                        keys = itertools.product(*[range(x) for x in dtype.shape])
                        for key in keys:
                            label = "%s%s" % (name, list(key))
                            array_key = (name, key)
                            self.__fields.append((label, array_key))
                    else:
                        self.__fields.append((name, (name,)))
            else:
                self.__fields = None

        if qt.qVersion() > "4.6":
            self.endResetModel()
        else:
            self.reset()

    def arrayData(self):
        """Returns the internal data.

        :rtype: numpy.ndarray of h5py.Dataset
        """
        return self.__data

    def setNumericFormat(self, numericFormat):
        """Set format string controlling how the values are represented in
        the table view.

        :param str numericFormat: Format string (e.g. "%.3f", "%d", "%-10.2f",
            "%10.3e").
            This is the C-style format string used by python when formatting
            strings with the modulus operator.
        """
        if qt.qVersion() > "4.6":
            self.beginResetModel()

        self.__format = numericFormat

        if qt.qVersion() > "4.6":
            self.endResetModel()
        else:
            self.reset()


class RecordTableView(qt.QTableView):
    """TableView using DatabaseTableModel as default model.
    """
    def __init__(self, parent=None):
        """
        Constructor

        :param parent: parent QWidget
        """
        qt.QTableView.__init__(self, parent)
        self.setModel(RecordTableModel())
        self.__multilineView = _MultiLineItem(self)

    def setArrayData(self, data):
        self.model().setArrayData(data)
        # TODO it would be nice to also fix fields
        # but using it only for string array is already very useful
        if issubclass(data.dtype.type, (numpy.string_, numpy.unicode_)):
            self.setItemDelegateForColumn(0, self.__multilineView)
        else:
            self.setItemDelegateForColumn(0, None)
