"""Node-scaling builder and exploratory results, separate from match configuration."""
import json
import math
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QFileDialog
from .experiments import build_experiment
from .model import parse_budget,openings
from .statistics import analyze


class ScalingGraph(QWidget):
    def __init__(self):
        super().__init__(); self.points=[]; self.setMinimumHeight(170)
    def paintEvent(self,event):
        painter=QPainter(self); painter.fillRect(self.rect(),QColor('#19232d'))
        painter.setPen(QColor('#b3c5cd')); painter.drawText(12,20,'Exploratory Elo of B over A / log node ratio; unbounded or missing estimates excluded')
        valid=[(ratio,-r['elo'],r) for ratio,r in self.points if r['elo'] is not None and math.isfinite(r['elo'])]
        if not valid: return
        max_x=max(math.log2(ratio) for ratio,_,_ in valid) or 1
        scale=max(100,max(abs(v) for _,v,_ in valid))
        for ratio,value,result in valid:
            x=40+math.log2(ratio)/max_x*(self.width()-80)
            y=self.height()/2-value/scale*(self.height()/2-35)
            painter.setPen(QPen(QColor('#78c4b5'),2)); painter.drawEllipse(int(x)-4,int(y)-4,8,8)
            interval=result['interval']
            if interval and all(math.isfinite(v) for v in interval):
                low,high=(-interval[1],-interval[0])
                y1=self.height()/2-max(-scale,min(scale,low))/scale*(self.height()/2-35)
                y2=self.height()/2-max(-scale,min(scale,high))/scale*(self.height()/2-35)
                painter.drawLine(int(x),int(y1),int(x),int(y2))
            painter.drawText(int(x),self.height()-10,str(ratio)+'×')


class ScalingPanel(QWidget):
    def __init__(self, window, runner):
        super().__init__(); self.window=window; self.runner=runner
        layout=QVBoxLayout(self)
        label=QLabel('Node Scaling Experiment · uses selected Engine A profile, opening suite, pairs, seed and playing MultiPV from Match Setup. Conditions run sequentially with identical paired openings.'); label.setWordWrap(True);layout.addWidget(label)
        row=QHBoxLayout(); self.base=QLineEdit('1M');self.ratios=QLineEdit('2, 5, 10, 25, 50, 100')
        row.addWidget(QLabel('Base nodes'));row.addWidget(self.base);row.addWidget(QLabel('Ratios'));row.addWidget(self.ratios);layout.addLayout(row)
        for title,callback in [('Build experiment',self.build),('Start / resume experiment',self.resume),('Pause experiment',runner.pause),('Export full experiment JSON',self.export)]:
            b=QPushButton(title);b.clicked.connect(callback);layout.addWidget(b)
        self.summary=QLabel('No experiment loaded.'); self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.graph=ScalingGraph();layout.addWidget(self.graph)
        self.table=QTableWidget(0,10);self.table.setHorizontalHeaderLabels(['Ratio','A nodes','B nodes','Games','A W/L/D','A score','B Elo','B Elo interval','Pairs / clusters','Status'])
        self.table.cellClicked.connect(self.open_condition);layout.addWidget(self.table)
        runner.changed.connect(self.refresh);self.refresh()
    def build(self):
        try:
            w=self.window
            state=build_experiment(w.selected_profiles()[0],parse_budget(self.base.text()),[int(v.strip()) for v in self.ratios.text().split(',')],openings(w.book.text()),w.pairs.value(),w.seed.value(),w.play_pv.value(),parse_budget(w.checkpoint.text()))
            for condition in state['conditions']:condition['silence_timeout_ms']=w.silence_timeout.value()*1000
            self.runner.create(state)
        except (ValueError,OSError) as exc:self.window.error(str(exc))
    def resume(self):
        try:self.window.cancel_analysis();self.runner.resume()
        except ValueError as exc:self.window.error(str(exc))
    def refresh(self):
        state=self.runner.state
        if not state:return
        self.summary.setText(state['label']+f" · condition {min(state['index']+1,len(state['conditions']))}/{len(state['conditions'])}. Intervals unavailable without sufficient independent openings. No fixed strength gain is assumed.")
        self.table.setRowCount(len(state['conditions']));self.graph.points=[]
        for row,c in enumerate(state['conditions']):
            r=analyze(c);self.graph.points.append((c['ratio'],r))
            ci=r['interval']; elo=r['elo']
            values=[str(c['ratio'])+'×',str(c['limits'][0]['value']),str(c['limits'][1]['value']),str(r['games']),f"{r['wins']}/{r['losses']}/{r['draws']}",f"{r['score']:.1%}" if r['score'] is not None else '—',f'{-elo:+.1f}' if elo is not None else '—',f'{-ci[1]:+.1f} to {-ci[0]:+.1f}' if ci else 'Unavailable',f"{r['pairs']} / {r['clusters']}",r['status']]
            for col,value in enumerate(values):self.table.setItem(row,col,QTableWidgetItem(value))
        self.graph.update()
    def open_condition(self,row,col):
        if self.window.tournament.active:
            self.window.error('Pause the experiment before opening another condition.');return
        sid=self.runner.state['conditions'][row]['id']
        self.window.archive_selector.addItem('Experiment condition '+str(row+1),sid)
        self.window.archive_selector.setCurrentIndex(self.window.archive_selector.count()-1)
        self.window.open_archive()
    def export(self):
        if not self.runner.state:return
        path,_=QFileDialog.getSaveFileName(self,'Export experiment',filter='JSON (*.json)')
        if path:
            ids={c['id'] for c in self.runner.state['conditions']}
            data=self.window.db.export()
            data['experiment']=self.runner.state
            data['condition_statistics']=[dict(tournament=c['id'],**analyze(c)) for c in self.runner.state['conditions']]
            for result in data['condition_statistics']:
                for key in ('elo','interval'):
                    value=result.get(key)
                    if isinstance(value,float) and not math.isfinite(value):result[key]='unbounded positive' if value>0 else 'unbounded negative'
                    if isinstance(value,tuple):result[key]=[v if math.isfinite(v) else ('unbounded positive' if v>0 else 'unbounded negative') for v in value]
            data['searches']=[r for r in data['searches'] if r.get('tournament') in ids]
            sids={r['id'] for r in data['searches']}
            data['snapshots']=[r for r in data['snapshots'] if r['id'] in sids]
            data['settings']={k:v for k,v in data['settings'].items() if k in {'tournament:'+i for i in ids}}
            try:
                from pathlib import Path
                Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8')
            except OSError as exc:self.window.error(str(exc))
