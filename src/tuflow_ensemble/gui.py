from PyQt6 import QtCore
from PyQt6.QtGui import QPalette, QColor, QFont, QPixmap, QIcon, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QTableWidget,
    QStyle,
    QMessageBox,

    QApplication,
    QWidget,
    QGridLayout,
    QFileDialog,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QHeaderView,
    QStyleFactory,
    QTableWidgetItem,
)
from PyQt6.QtCore import QObject, QThreadPool, QRunnable, pyqtSignal, pyqtSlot
import os
import sys
import te
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from models import POLine
from table import TableView
from graph import GraphView


# from tuflow_ensemble import te

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller.
    From https://stackoverflow.com/questions/31836104/pyinstaller-and-onefile-how-to-include-an-image-in-the-exe-file"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class App(QWidget):
    def __init__(self):
        super().__init__()

        self.input_directory = None
        self.title = "StormViewer"
        # self.iconPath = resource_path("assets/rain-svgrepo-com.svg")

        # self.setWindowIcon(QIcon(self.iconPath))

        self.threadpool = QThreadPool()
        self.main_layout = QGridLayout()
        self.processor = Processor()

        self.input_1 = None
        self.table_view = TableView()
        self.graph_view = GraphView()

        # Connect table row click with graph update func

        self.table_view.table.cellClicked.connect(self.update_graph_view)

        self.initUI()

    def initUI(self):
        # self.setGeometry(self.left, self.top, self.width, self.height)
        self.setWindowTitle("StormViewer")

        self.setUpMainWindow()
        self.show()

    def setUpMainWindow(self):
        """ Layouts for main window"""
        self.main_layout.addWidget(self.table_view, 0, 1)
        if self.input_1 is None:
            self.input_1 = self.input_controls()
            self.main_layout.addWidget(self.input_1, 0, 0)

        self.main_layout.addWidget(self.graph_view, 1, 0, 1, 2)

        self.setLayout(self.main_layout)

    def input_controls(self):

        widget = QWidget()
        widget.setFixedWidth(150)
        widget.setFixedHeight(180)

        layout = QVBoxLayout()

        icon = self.app_icon_label()

        browse_input = QPushButton("Select Results\n Folder")
        browse_input.clicked.connect(self.read_input_path)

        create_plots = QPushButton("Create Plots")
        create_plots.setFixedHeight(30)
        create_plots.clicked.connect(self.create_plots)

        layout.addWidget(icon)
        layout.addWidget(browse_input)
        layout.addWidget(create_plots)

        layout.addStretch()
        widget.setLayout(layout)

        return widget

    def app_icon_label(self):

        """ Rain Cloud Icon"""
        # Icon and file inputs cell

        iconPath = resource_path("assets/rain-svgrepo-com.svg")

        # Add App Icon

        app_icon_label = QLabel(self)
        app_icon = QPixmap(iconPath).scaledToWidth(80)

        # Format app icon

        app_icon_label.setPixmap(app_icon)
        app_icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        return app_icon_label

    def graph_view(self):
        widget = QWidget()

        layout = QVBoxLayout()
        separator = self.separator()

        layout.addWidget(separator)

        canvas = self.create_canvas()
        layout.addWidget(canvas)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def separator(self):

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        return separator

    # CONTROLLER FUNCTIONS

    def read_input_path(self):

        self.input_directory = str(QFileDialog.getExistingDirectory(self, "Select Input Folder"))
        self.processor = Processor(self.input_directory)
        self.threadpool.start(self.processor.run)

        self.processor.signals.finished.connect(self.update_table_view)

    def create_plots(self):

        self.threadpool.start(self.processor.plot)
        self.processor.signals.finished.connect(self.update_graph_view)


    def update_table_view(self):
        table_data = []
        storms = self.processor.po_lines

        for storm in storms:

            crit_storm = f"{storm.crit_duration}m, {storm.crit_tp}"
            storm_data = [storm.id, storm.event, crit_storm, storm.crit_flow]
            assert len(storm_data) == 4

            table_data.append(storm_data)

        self.table_view.data = table_data
        self.table_view.update_table()

        self.table_view.directory = self.input_directory
        self.table_view.update_label()

    def update_graph_view(self):
        if self.processor.figs is not None:
            self.graph_view.update_graph(self.processor.figs[self.table_view.selected_row])

### Canvas class ###
class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, fig=Figure(), width=5, height=4, dpi=200):
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


### Backend Script Connections ###
class Processor(QRunnable):
    def __init__(self, input_directory=None):
        super(Processor).__init__()
        self.input_directory = input_directory
        self.signals = WorkerSignals()
        self.po_lines = None
        self.figs = None

    def run(self):
        self.po_lines = te.read_input_directory(self.input_directory)

        if self.po_lines:
            self.signals.finished.emit()
        else:
            self.signals.error.emit()

    def plot(self):

        if not self.po_lines:
            raise ValueError("Cannot plot as no POLine objects have been generated yet.")

        self.figs = []

        for po_line in self.po_lines:
            po_line.plot()
            self.figs.append(po_line.fig)

        self.signals.finished.emit()


class WorkerSignals(QObject):
    """
    This class holds signals for QRunnable Object. Supports:

    finished
        Send signal that QRunnable has finished execution.
    error
        Send error signal if QRunnable has encountered an error.

    """

    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    ex = App()
    ex.show()
    sys.exit(app.exec())
