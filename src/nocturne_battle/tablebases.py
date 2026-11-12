"""Shared Syzygy setup using each engine's advertised UCI options."""
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QLineEdit,QPushButton,QCheckBox,QFileDialog
from nocturne.gui.uci_connection import UciConnection
from .model import Profile,executable_hash


class TablebaseDialog(QDialog):
    def __init__(self,profiles,parent=None):
        super().__init__(parent);self.setWindowTitle('Tablebases for both engines');self.resize(600,350)
        self.originals=[asdict(p) for p in profiles];self.profiles=[Profile(**p) for p in self.originals];self.connection=None;self.index=0;self.messages=[]
        layout=QVBoxLayout(self)
        note=QLabel('Select your Syzygy folder for the next new match. The folder must contain .rtbw files; .rtbz files provide distance-to-zero information. Five-piece sets are supported by engines that advertise SyzygyPath. Other tablebase formats require their own compatible engine settings.');note.setWordWrap(True);layout.addWidget(note)
        self.path=QLineEdit();layout.addWidget(self.path)
        browse=QPushButton('Choose tablebase folder…');layout.addWidget(browse)
        browse.clicked.connect(self.browse)
        self.replace=QCheckBox('Replace existing tablebase paths too');layout.addWidget(self.replace)
        self.status=QLabel('Existing paths are kept by default. Each engine is checked for support before applying settings.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.apply=QPushButton('Apply to both engines');layout.addWidget(self.apply);self.apply.clicked.connect(self.begin)
        close=QPushButton('Cancel');layout.addWidget(close);close.clicked.connect(self.reject)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(lambda:self.fail('Engine did not answer within 15 seconds.'))
    def browse(self):
        path=QFileDialog.getExistingDirectory(self,'Choose folder containing Syzygy files',self.path.text())
        if path:self.path.setText(path)
    def begin(self):
        folder=Path(self.path.text())
        if not folder.is_dir() or not any(folder.glob('*.rtbw')):
            self.status.setText('Select a folder containing Syzygy .rtbw files. Engines do not automatically search subfolders.');return
        self.profiles=[Profile(**dict(p,options=dict(p['options']))) for p in self.originals];self.folder=str(folder.resolve());self.index=0;self.messages=[];self.apply.setEnabled(False);self.next()
    def next(self):
        if self.index==len(self.profiles):self.accept();return
        p=self.profiles[self.index]
        key=next((k for k in p.options if k.lower()=='syzygypath'), 'SyzygyPath')
        if p.options.get(key) and str(p.options[key])!='<empty>' and not self.replace.isChecked():
            self.messages.append(p.name+': existing path kept');self.index+=1;self.next();return
        try:
            if executable_hash(p.path)!=p.identity:raise ValueError('Engine file changed; load and test it again.')
            self.connection=UciConnection(self);self.connection.discovered.connect(self.discovered);self.connection.failed.connect(self.fail)
            self.status.setText('Checking '+p.name+'…');self.timer.start(15000);self.connection.launch(p.path,p.arguments)
        except (OSError,ValueError) as exc:self.fail(str(exc))
    def discovered(self,data):
        self.timer.stop();self.connection.close();p=self.profiles[self.index]
        options=data['options'];key=next((k for k in options if k.lower()=='syzygypath'),None)
        if key:
            p.options={k:v for k,v in p.options.items() if k.lower()!='syzygypath'}
            p.options[key]=self.folder
            limit=next((k for k in options if k.lower()=='syzygyprobelimit'),None)
            if limit:p.options[limit]=max(options[limit].minimum,min(5,options[limit].maximum))
            self.messages.append(p.name+': Syzygy folder set, probe limit up to 5 pieces')
        else:self.messages.append(p.name+': SyzygyPath unsupported; unchanged')
        self.index+=1;QTimer.singleShot(0,self.next)
    def fail(self,message):
        self.timer.stop()
        if self.connection:self.connection.close()
        self.status.setText(str(message)+' No saved settings changed.');self.apply.setEnabled(True)
    def done(self,result):
        self.timer.stop()
        if self.connection:self.connection.close()
        super().done(result)
