"""Human-readable minutes and seconds with legacy settings compatibility."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QSpinBox,QDoubleSpinBox


class MinutesSeconds(QWidget):
    changed=Signal()
    def __init__(self):
        super().__init__();layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.minutes=QSpinBox();self.minutes.setRange(0,1440);self.minutes.setSuffix(' min')
        self.seconds=QDoubleSpinBox();self.seconds.setRange(0,59.999);self.seconds.setDecimals(3);self.seconds.setSuffix(' sec')
        self.minutes.setToolTip('Whole minutes of starting time.')
        self.seconds.setToolTip('Additional seconds of starting time; use 10 here for a ten-second game.')
        layout.addWidget(self.minutes);layout.addWidget(self.seconds)
        self.minutes.valueChanged.connect(self.changed);self.seconds.valueChanged.connect(self.changed)
        self.setValue(10/60)
    def value(self):return self.minutes.value()+self.seconds.value()/60
    def setValue(self,minutes):
        milliseconds=round(minutes*60000)
        self.minutes.setValue(milliseconds//60000);self.seconds.setValue(milliseconds%60000/1000)
