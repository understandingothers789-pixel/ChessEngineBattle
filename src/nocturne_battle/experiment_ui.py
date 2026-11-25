"""Node-scaling builder and exploratory results, separate from match configuration."""
import json
import math

from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QFileDialog,QAbstractItemView,QMessageBox,QHeaderView
from .experiments import build_experiment
from .model import parse_budget,openings
from .statistics import analyze
from .runtime import playing_multipv
from .studio import describe_limit


class ScalingGraph(QWidget):
    def __init__(self):
        super().__init__(); self.points=[]; self.setMinimumHeight(170)
    def paintEvent(self,event):
        painter=QPainter(self); painter.fillRect(self.rect(),QColor('#19232d'))
        painter.setPen(QColor('#b3c5cd')); painter.drawText(12,20,'Exploratory Elo of B over A / log node ratio; unbounded or missing estimates excluded')
        valid=[(ratio,-r['pair_elo'],r) for ratio,r in self.points if r['pair_elo'] is not None and math.isfinite(r['pair_elo'])]
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
        title = QLabel('Match experiments')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        label = QLabel('Queue the current Match Setup, then change either engine, limit or MultiPV and queue another. Every condition uses the first setup’s paired openings and match rules.')
        label.setWordWrap(True)
        label.setObjectName('muted')
        layout.addWidget(label)
        queue_actions = QHBoxLayout()
        self.queue_button = QPushButton('Queue current setup')
        self.queue_button.clicked.connect(self.queue_setup)
        queue_actions.addWidget(self.queue_button)
        self.remove_button = QPushButton('Remove queued condition')
        self.remove_button.clicked.connect(self.remove_condition)
        queue_actions.addWidget(self.remove_button)
        layout.addLayout(queue_actions)
        row = QHBoxLayout()
        self.base = QLineEdit('1M')
        self.ratios = QLineEdit('2, 5, 10, 25, 50, 100')
        self.base.setToolTip('Engine A’s node limit per move. For example, 1M means 1,000,000 nodes.')
        self.ratios.setToolTip('Comma-separated multipliers for Engine B’s node limit.')
        row.addWidget(QLabel('Base nodes'))
        row.addWidget(self.base)
        row.addWidget(QLabel('Ratios'))
        row.addWidget(self.ratios)
        layout.addLayout(row)
        actions = QHBoxLayout()
        self.build_button = QPushButton('Build node scaling')
        self.build_button.setToolTip('Build a separate experiment using Engine A for both sides with fixed node ratios.')
        self.run_button = QPushButton('Start / resume')
        self.pause_button = QPushButton('Pause')
        self.export_button = QPushButton('Export JSON…')
        for control, callback in [
            (self.build_button, self.build), (self.run_button, self.resume),
            (self.pause_button, runner.pause), (self.export_button, self.export),
        ]:
            control.clicked.connect(callback)
            actions.addWidget(control)
        self.run_button.setObjectName('primaryAction')
        layout.addLayout(actions)
        self.summary=QLabel('No experiment loaded.'); self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.graph=ScalingGraph();layout.addWidget(self.graph)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Engine A', 'Engine B', 'Progress', 'A − B Elo'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        self.table.setColumnWidth(2, 94)
        self.table.setColumnWidth(3, 122)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellActivated.connect(self.open_condition)
        self.table.itemSelectionChanged.connect(self.update_actions)
        self.table.setToolTip('Double-click a condition or press Enter to review its games.')
        layout.addWidget(self.table)
        runner.changed.connect(self.refresh)
        window.tournament.changed.connect(self.update_actions)
        self.refresh()
    def confirm_new_queue(self):
        if not self.runner.state or not self.runner.state['conditions']:
            return True
        return QMessageBox.question(self, 'Replace experiment queue',
                                    'Start a new queue? The current conditions remain in Saved Matches.') == QMessageBox.StandardButton.Yes

    def queue_setup(self):
        try:
            append = self.runner.can_append()
            shared = (self.runner.state['conditions'][0]
                      if append and self.runner.state['conditions'] else None)
            condition = self.window.prepared_match(shared=shared)
            if not append and not self.confirm_new_queue():
                return
            self.runner.enqueue(condition, replace=not append)
        except (ValueError, OSError, ArithmeticError) as exc:
            self.window.error(str(exc))

    def remove_condition(self):
        row = self.table.currentRow()
        if not self.runner.can_append() or row < 0:
            return
        # Only draft queue entries can be removed. Their saved match copies stay
        # available in the library, just as when replacing a queue.
        self.runner.state['conditions'].pop(row)
        self.runner.save()

    def build(self):
        try:
            w=self.window
            state=build_experiment(w.selected_profiles()[0],parse_budget(self.base.text()),[int(v.strip()) for v in self.ratios.text().split(',')],openings(w.book.text()),w.pairs.value(),w.seed.value(),w.play_pv.value(),parse_budget(w.checkpoint.text()))
            if not self.confirm_new_queue():
                return
            for condition in state['conditions']:
                condition['silence_timeout_ms'] = w.silence_timeout.value() * 1000
                condition['opening_book'] = w.book.text().strip()
            self.runner.create(state)
        except (ValueError,OSError,ArithmeticError) as exc:self.window.error(str(exc))
    def resume(self):
        try:
            self.window.cancel_analysis()
            self.window.follow_live = True
            self.runner.resume()
        except ValueError as exc:
            self.window.error(str(exc))
    def update_actions(self):
        state = self.runner.state
        running = self.window.tournament.active or self.runner.active
        available = bool(state and state['index'] < len(state['conditions']))
        editable = self.runner.can_append()
        self.queue_button.setText('Queue current setup' if editable or not state else 'New queue from current setup')
        self.queue_button.setEnabled(not running)
        self.remove_button.setEnabled(editable and 0 <= self.table.currentRow() < len(state['conditions']))
        self.build_button.setEnabled(not running)
        self.run_button.setEnabled(available and not running)
        self.pause_button.setEnabled(self.runner.active or
                                     (self.window.tournament.active and self.runner.owns_current_condition()))
        self.export_button.setEnabled(bool(state and state['conditions']))

    def refresh(self):
        state = self.runner.state
        conditions = state['conditions'] if state else []
        mixed = bool(state and state.get('kind') == 'mixed')
        self.graph.setVisible(not mixed and bool(conditions))
        self.graph.points = []
        if conditions:
            complete = sum(c['index'] >= len(c['games']) for c in conditions)
            self.summary.setText(f"{state['label']} · {complete}/{len(conditions)} conditions complete. "
                                 "Estimates use completed opening pairs.")
        else:
            self.summary.setText('Queue a match setup or build a node-scaling experiment.')
        self.table.setRowCount(len(conditions))
        for row, condition in enumerate(conditions):
            result = analyze(condition)
            if 'ratio' in condition:
                self.graph.points.append((condition['ratio'], result))
            per_side = [
                f"{profile['name']}\n{describe_limit(limit)}\nMultiPV {playing_multipv(condition, side)}"
                for side, (profile, limit) in enumerate(zip(condition['profiles'], condition['limits']))
            ]
            # Use the same score basis for the estimate and its interval.
            elo = result['pair_elo']
            interval = result['interval']
            estimate = f'{elo:+.0f}' if elo is not None and math.isfinite(elo) else (
                '+∞' if elo == math.inf else '−∞' if elo == -math.inf else '—')
            bounds = f'{interval[0]:+.0f} to {interval[1]:+.0f}' if interval else '—'
            total = len(condition['games'])
            status = ('Complete' if condition['index'] >= total else
                      'Running' if self.window.tournament.active and self.window.tournament.state['id'] == condition['id'] else
                      'Paused' if result['games'] or condition['index'] else 'Queued')
            progress = f"{status}\n{result['games']}/{total} games\n{result['pairs']} pairs"
            score = estimate + (f'\n95% {bounds}' if interval else '')
            for col, value in enumerate([*per_side, progress, score]):
                item = QTableWidgetItem(value)
                tip = value
                if col == 2:
                    tip += f"\nEngine A wins/draws/losses: {result['wins']}/{result['draws']}/{result['losses']}"
                if col == 3:
                    tip += '\nElo estimate uses completed opening pairs.'
                    if not interval:
                        tip += ' The interval needs at least ten distinct openings and varying scores.'
                item.setToolTip(tip)
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()
        self.graph.update()
        self.update_actions()

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
                for key in ('elo', 'pair_elo', 'interval'):
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
