"""Presentation widgets for the match studio; no engine or game mutations."""
import math
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QVBoxLayout,QHBoxLayout,QProgressBar,QSizePolicy


def label(text,name):
    widget=QLabel(text);widget.setObjectName(name);return widget


class EngineName(QLabel):
    def paintEvent(self,event):
        painter=QPainter(self);painter.setPen(self.palette().color(self.foregroundRole()))
        text=self.fontMetrics().elidedText(self.text(),Qt.TextElideMode.ElideMiddle,self.width())
        painter.drawText(self.rect(),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,text)


class EngineScoreboard(QWidget):
    def __init__(self,controls):
        super().__init__();layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(5)
        row=QHBoxLayout();row.setSpacing(12);layout.addLayout(row)
        self.names=[];self.points=[];self.details=[];self.clocks=[];self.cards=[]
        for side,control in enumerate(controls):
            card=QFrame();card.setObjectName('engineCard');card.setProperty('side','AB'[side]);box=QVBoxLayout(card);box.setContentsMargins(12,8,12,8);box.setSpacing(3)
            top=QHBoxLayout();top.addWidget(label('ENGINE '+'AB'[side],'eyebrow'));top.addStretch()
            control.setText('Load engine');control.setObjectName('engineLoad');top.addWidget(control);box.addLayout(top)
            name=EngineName('Choose a UCI engine');name.setObjectName('engineName');name.setMinimumWidth(0);name.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
            middle=QHBoxLayout();points=label('0','scoreValue');clock=label('','engineClock');middle.addWidget(name,1);middle.addWidget(points);box.addLayout(middle)
            detail=label('Ready to configure','cardDetail');bottom=QHBoxLayout();bottom.addWidget(detail,1);bottom.addWidget(clock);box.addLayout(bottom)
            row.addWidget(card,1);self.names.append(name);self.points.append(points);self.details.append(detail);self.clocks.append(clock);self.cards.append(card)
        self.progress=QProgressBar();self.progress.setObjectName('matchProgress');self.progress.setRange(0,100);self.progress.setValue(0);self.progress.setTextVisible(False);self.progress.setFixedHeight(5);layout.addWidget(self.progress)
    def configure_names(self,profiles):
        for side,p in enumerate(profiles):
            name=p['name'] if isinstance(p,dict) else p.name
            self.names[side].setText(name);self.names[side].setToolTip(name)
    def update_match(self,state,summary):
        self.configure_names(state['profiles'])
        for side in range(2):
            wins=summary['wins'] if side==0 else summary['losses'];losses=summary['losses'] if side==0 else summary['wins'];draws=summary['draws']
            self.points[side].setText(f'{wins+draws/2:g}')
            self.details[side].setText(f'{wins} wins   ·   {losses} losses   ·   {draws} draws')
        complete=sum(g['result']!='*' for g in state['games']);self.progress.setMaximum(len(state['games']));self.progress.setValue(complete)
        self.progress.setToolTip(f'{complete} of {len(state["games"])} games completed')
    def set_clocks(self,a,b):
        for widget,value in zip(self.clocks,(a,b)):widget.setText(value)


class ResultCards(QWidget):
    def __init__(self):
        super().__init__();layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(10)
        layout.addWidget(label('MATCH RESULTS','eyebrow'))
        row=QHBoxLayout();layout.addLayout(row);self.values=[];self.descriptions=[]
        for title,value,description in [('Game score','—','Completed games'),('Opening pairs','—','Completed two-game pairs'),('Rough Elo','—','Engine A minus Engine B')]:
            frame=QFrame();frame.setObjectName('resultCard');box=QVBoxLayout(frame);box.setContentsMargins(12,12,12,12)
            box.addWidget(label(title,'cardDetail'));v=label(value,'resultValue');box.addWidget(v);d=label(description,'cardDetail');d.setWordWrap(True);box.addWidget(d)
            row.addWidget(frame,1);self.values.append(v);self.descriptions.append(d)
        note=label('Results update automatically. Elo is an estimate, not a formal rating.','muted');note.setWordWrap(True);layout.addWidget(note)
    def update_match(self,r):
        self.values[0].setText(f"{r['wins']+r['draws']/2:g} : {r['losses']+r['draws']/2:g}")
        self.descriptions[0].setText(f"A {r['wins']}W / {r['losses']}L / {r['draws']}D\nB {r['losses']}W / {r['wins']}L / {r['draws']}D")
        self.values[1].setText(f"{r['pair_wins']} : {r['pair_losses']}")
        self.descriptions[1].setText(f"A wins : B wins\n{r['pair_draws']} drawn pairs")
        elo=r['elo'];self.values[2].setText('—' if elo is None else (f'{elo:+.0f}' if math.isfinite(elo) else ('+∞' if elo>0 else '−∞')))
        self.descriptions[2].setText('No completed games' if elo is None else ('A − B · early estimate' if math.isfinite(elo) else 'No finite estimate yet'))
