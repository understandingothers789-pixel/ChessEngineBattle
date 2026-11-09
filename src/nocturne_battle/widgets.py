"""Standalone native match and exact-position search inspection workspace."""
from dataclasses import asdict
import csv
import json
import math
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QStandardPaths, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QSplitter, QScrollArea, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, QPlainTextEdit, QSlider)
from nocturne.core.game import Game
from nocturne.core.board import Board
from nocturne.engine.uci_types import score_label
from nocturne.gui.board import BoardWidget
from nocturne.gui.candidates import CandidatePanel
from nocturne.gui.moves import MoveText
from nocturne.gui.theme import stylesheet
from nocturne.gui.uci_connection import UciConnection
from nocturne.gui.widgets import EvaluationBar
from nocturne.snapshots import node_label

from .history import compare, select_checkpoint
from .model import Database, Profile, Limit, executable_hash, openings, schedule



def button(text, callback, layout):
    control = QPushButton(text)
    control.clicked.connect(callback)
    layout.addWidget(control)
    return control


class TablebaseFolderEdit(QLineEdit):
    def mousePressEvent(self,event):
        super().mousePressEvent(event)
        if event.button()==Qt.MouseButton.LeftButton:
            path=QFileDialog.getExistingDirectory(self,'Choose Syzygy tablebase folder',self.text())
            if path:self.setText(path)


class ProfileDialog(QDialog):
    def __init__(self, parent=None, existing=None, selected_path=None):
        super().__init__(parent)
        self.setWindowTitle('Add a chess engine' if not existing else 'Engine settings')
        self.resize(650, 520)
        self.profile = None
        self.discovered = None
        self.connection = UciConnection(self)
        self.connection.discovered.connect(self.discover)
        self.connection.failed.connect(self.error)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.name = QLineEdit(existing.name if existing else Path(selected_path).stem if selected_path else '')
        self.path = QLineEdit(existing.path if existing else selected_path or '')
        self.args = QLineEdit(json.dumps(existing.arguments if existing else []))
        self.options = QPlainTextEdit(json.dumps(existing.options if existing else {'Threads': 2, 'Hash': 1024}, indent=2))
        form.addRow('Profile name', self.name)
        form.addRow('Executable', self.path)
        button('Choose a different engine file…', self.browse, layout)
        help_text = QLabel('1. Choose your engine file.  2. Click Test engine.  3. Save to use it in matches. Testing runs the executable you selected.')
        help_text.setWordWrap(True);layout.addWidget(help_text)
        advanced = QGroupBox('Expert settings (optional)')
        advanced.setCheckable(True); advanced.setChecked(False)
        advanced_layout = QVBoxLayout(advanced)
        self.args.hide(); self.options.hide()
        advanced_layout.addWidget(self.args); advanced_layout.addWidget(self.options)
        advanced.toggled.connect(self.args.setVisible); advanced.toggled.connect(self.options.setVisible)
        self.raw_enabled = advanced
        layout.addWidget(advanced)
        self.option_widgets = {}
        self.visual_form = QFormLayout()
        option_container = QWidget(); option_container.setLayout(self.visual_form)
        option_scroll = QScrollArea(); option_scroll.setWidgetResizable(True)
        option_scroll.setWidget(option_container)
        options_group = QGroupBox('Engine options (optional — defaults work for most users)')
        options_group.setCheckable(True);options_group.setChecked(False)
        options_layout=QVBoxLayout(options_group);options_layout.addWidget(option_scroll)
        option_scroll.hide();options_group.toggled.connect(option_scroll.setVisible)
        layout.addWidget(options_group)
        self.existing = existing

        self.status = QLabel('Click Test engine to check that this file supports chess-engine communication.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.test_button = button('Test engine', self.validate, layout)
        self.option_list = QPlainTextEdit()
        self.option_list.setReadOnly(True)
        advanced_layout.addWidget(self.option_list)
        self.option_list.hide(); advanced.toggled.connect(self.option_list.setVisible)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Save).setText('Save engine')
        controls.accepted.connect(self.save)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        from .help import install_tooltips
        install_tooltips(self)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select UCI executable')
        if path:
            self.path.setText(path)
            if not self.name.text():
                self.name.setText(Path(path).stem)

    def error(self, text):
        self.status.setText(text)

    def validate(self):
        try:
            args = json.loads(self.args.text())
            if not isinstance(args, list) or any(not isinstance(x, str) for x in args):
                raise ValueError('Arguments must be a JSON array of strings')
            self.discovered = None
            self.validation = (self.path.text(), self.args.text())
            self.connection.launch(self.path.text(), args)
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def discover(self, data):
        self.discovered = data
        while self.visual_form.rowCount():
            self.visual_form.removeRow(0)
        self.option_widgets = {}
        for name, option in data['options'].items():
            if option.kind == 'button':
                continue
            defaults = {'threads': 2, 'hash': 1024, 'skill level': option.maximum, 'uci_limitstrength': False}
            value = self.existing.options.get(name, option.default) if self.existing else defaults.get(name.lower(), option.default)
            if option.kind == 'spin':
                control = QSpinBox(); control.setRange(option.minimum, min(option.maximum, 2147483647))
                control.setValue(int(value))
                if name.lower() == 'hash': control.setSuffix(' MB')
            elif option.kind == 'check':
                control = QCheckBox(); control.setChecked(str(value).lower() == 'true')
            elif option.kind == 'combo':
                control = QComboBox(); control.addItems(option.choices); control.setCurrentText(str(value))
            else:
                control = (TablebaseFolderEdit if name.lower()=='syzygypath' else QLineEdit)('' if value == '<empty>' else str(value))
            tips = {'threads':'Number of CPU threads the engine uses while searching. More threads use more CPU.', 'hash':'Memory reserved for the engine’s search cache, in megabytes. 1024 MB is 1 GiB.', 'skill level':'Stockfish playing strength: the maximum value selects full strength. Lower values deliberately weaken play.', 'uci_limitstrength':'When enabled, limits Stockfish strength to the configured Elo. Leave off for full strength.', 'uci_elo':'Target playing strength when UCI_LimitStrength is enabled; ignored when it is off.', 'syzygypath':'Folder containing Syzygy endgame tablebase files. These let the engine use exact results for supported positions.', 'multipv':'Number of candidate lines to search. More lines can reduce playing strength at the same budget.'}
            from .engine_help import HELP
            control.setToolTip(HELP.get(name,tips.get(name.lower(), f'{name}: a setting advertised by this engine. Its documentation is needed to explain this custom option accurately.')))
            self.option_widgets[name] = control
            self.visual_form.addRow(name, control)
            if name.lower() == 'syzygypath':
                browse = QPushButton('Browse tablebase folder…')
                def choose_syzygy(checked=False, c=control):
                    path = QFileDialog.getExistingDirectory(self, 'Choose Syzygy tablebase folder', c.text())
                    if path: c.setText(path)
                browse.clicked.connect(choose_syzygy)
                self.visual_form.addRow('', browse)
            if name.lower() in ('evalfile', 'evalfilesmall', 'weightsfile'):
                browse = QPushButton('Choose network…')
                def choose(checked=False, c=control):
                    path, _ = QFileDialog.getOpenFileName(self, 'Choose network file')
                    if path: c.setText(path)
                browse.clicked.connect(choose)
                self.visual_form.addRow('', browse)
        from .help import install_tooltips
        install_tooltips(self)
        self.status.setText('Ready: ' + data['name'] + '. Click Save engine to finish. Engine options can be left at their defaults.')
        self.option_list.setPlainText('\n'.join(f'{o.name}: {o.kind}, default={o.default}, '
            f'range={o.minimum}–{o.maximum}, choices={o.choices}' for o in data['options'].values()))

    def save(self):
        try:
            if not self.discovered or self.validation != (self.path.text(), self.args.text()):
                raise ValueError('Validate this executable and arguments before saving')
            if not self.name.text().strip():
                raise ValueError('Enter a profile name')
            options = json.loads(self.options.toPlainText()) if self.raw_enabled.isChecked() else {
                name: (control.value() if isinstance(control, QSpinBox) else
                       control.isChecked() if isinstance(control, QCheckBox) else
                       control.currentText() if isinstance(control, QComboBox) else control.text())
                for name, control in self.option_widgets.items()}

            # Stockfish advertises embedded NNUE filenames that need not exist on
            # disk. Only explicitly overridden paths are external cache inputs.
            if not self.raw_enabled.isChecked():
                for name in list(options):
                    if name.lower() in ('evalfile', 'evalfilesmall', 'weightsfile'):
                        default = self.discovered['options'][name].default
                        default = '' if default == '<empty>' else default
                        overridden = self.existing and name in self.existing.options
                        if not overridden and options[name] == default:
                            del options[name]
            if not isinstance(options, dict):
                raise ValueError('Options must be a JSON object')
            for name, value in options.items():
                if name not in self.discovered['options']:
                    raise ValueError('Unsupported option: ' + name)
                self.discovered['options'][name].validate(value)
            self.profile = Profile(self.name.text(), str(Path(self.path.text()).absolute()), options,
                json.loads(self.args.text()), executable_hash(self.path.text()), self.discovered['name'])
            self.profile.networks = self.profile.network_files()
            self.connection.close()
            self.accept()
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def done(self, code):
        self.connection.close()
        super().done(code)


class AnalysisPanel(QWidget):
    selected = Signal()
    preview = Signal(int, int)
    preview_end = Signal()

    def __init__(self, title):
        super().__init__()
        self.records = []
        self.record = None
        self.pinned = False
        layout = QVBoxLayout(self)
        self.title = QLabel(title)
        layout.addWidget(self.title)
        self.run = QComboBox()
        self.run.currentIndexChanged.connect(self.choose_run)
        layout.addWidget(self.run)
        self.checkpoint = QComboBox()
        self.checkpoint.currentIndexChanged.connect(self.choose)
        layout.addWidget(self.checkpoint)
        navigation = QHBoxLayout()
        button('Previous',lambda:self.checkpoint.setCurrentIndex(max(0,self.checkpoint.currentIndex()-1)),navigation)
        button('Next',lambda:self.checkpoint.setCurrentIndex(min(len(self.records)-1,self.checkpoint.currentIndex()+1)),navigation)
        button('Final result',lambda:self.checkpoint.setCurrentIndex(len(self.records)) if self.final_record else None,navigation)
        layout.addLayout(navigation)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.valueChanged.connect(self.checkpoint.setCurrentIndex)
        layout.addWidget(self.timeline)
        self.final_record = None
        self.pv_rank = QSpinBox()
        self.pv_rank.setRange(1, 5)
        self.pv_rank.setPrefix('Compare PV #')
        self.pv_rank.valueChanged.connect(self.selected)
        layout.addWidget(self.pv_rank)
        self.details = QLabel('No compatible analysis for this exact position.')
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.panel = CandidatePanel(MoveText(auto_fit=True))
        self.panel.show_line_depth = True
        self.panel.show_details = False
        self.panel.show_seldepth = True
        self.panel.preview.connect(self.preview)
        self.panel.preview_end.connect(self.preview_end)
        self.panel.set_maia(enabled=False)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.panel)
        layout.addWidget(scroll)
        self.board = BoardWidget()
        self.board.interactive = False
        self.board.setMinimumSize(230, 230)
        self.board.hide()
        layout.addWidget(self.board)
        pin = QCheckBox('Pin preview')
        self.pin_control=pin
        pin.toggled.connect(self.pin)
        layout.addWidget(pin)

    def pin(self, value):
        self.pinned = value
        if not value:
            self.preview_end.emit()

    def load(self, records, turn, runs=None):
        previous = self.run.currentData()
        self.all_records = records
        self.turn = turn
        self.run.blockSignals(True)
        self.run.clear()
        if runs is None:
            runs = list({r['id']: r for r in records}.values())[::-1]
        self.run_metadata = {run['id']:run for run in runs}
        for run in runs:
            from datetime import datetime
            label = (f"{datetime.fromtimestamp(run['timestamp']).strftime('%Y-%m-%d %H:%M:%S')} · "
                     f"{run.get('kind', 'continuous')} · {run['provenance']} · {node_label(run['limit']['value']) if run['limit']['mode']=='nodes' else run['limit']['value']} {run['limit']['mode']} · "
                     f"PV{run['multipv']} · {run['status']} · {run['id'][:8]}")
            self.run.addItem(label, run['id'])
            self.run.setItemData(self.run.count()-1, str(run), Qt.ItemDataRole.ToolTipRole)
        index = self.run.findData(previous)
        self.run.setCurrentIndex(max(0, index))
        self.run.blockSignals(False)
        self.choose_run()

    def choose_run(self):
        sid = self.run.currentData()
        previous = self.record['requested'] if self.record and self.record['id'] == sid else None
        self.records = sorted([r for r in getattr(self, 'all_records', []) if r['id'] == sid], key=lambda r:r['requested'])
        self.checkpoint.blockSignals(True)
        self.checkpoint.clear()
        for record in self.records:
            self.checkpoint.addItem(f"{node_label(record['requested'])} → {node_label(record['actual'])} actual · "
                f"{record['provenance']} · PV{record['multipv']} · {record['status']}")
        run = getattr(self,'run_metadata',{}).get(sid,{})
        result = run.get('final_result',{})
        lines = result.get('lines',{})
        self.final_record = None
        if lines:
            actual = max((line.get('nodes',0) for line in lines.values()),default=0)
            self.final_record = dict(run,lines=lines,requested=run['limit']['value'] if run['limit']['mode']=='nodes' else max(1,actual),
                actual=actual,complete=len(lines)>=run['multipv'],final=True)
            self.checkpoint.addItem('Final result · bestmove '+str(result.get('move')))
        self.timeline.blockSignals(True); self.timeline.setRange(0,max(0,len(self.records)-1)); self.timeline.blockSignals(False)
        index = next((i for i,r in enumerate(self.records) if r['requested'] == previous), len(self.records)-1)
        self.checkpoint.setCurrentIndex(index)
        self.checkpoint.blockSignals(False)
        self.choose()

    def choose(self):
        index = self.checkpoint.currentIndex()
        self.record = self.records[index] if 0 <= index < len(self.records) else self.final_record if index == len(self.records) else None
        if index < len(self.records):
            self.timeline.blockSignals(True);self.timeline.setValue(index);self.timeline.blockSignals(False)
        self.panel.clear()
        if self.record:
            record = self.record
            self.panel.set_multipv(record['multipv'])
            for line in record['lines'].values():
                self.panel.update_line(line, self.turn)
                rank = line['multipv']
                if rank in self.panel.rows:
                    self.panel.rows[rank][2].setToolTip(
                        f"Freshness: {record.get('rank_freshness',{}).get(str(rank),record.get('rank_freshness',{}).get(rank,'not recorded for legacy data'))}\nReported {line.get('nodes', 0):,} nodes · {line.get('nps', 0):,} nps · "
                        f"{line.get('seconds', 0):g}s · depth {line.get('depth', 0)} / seldepth {line.get('seldepth', 0)}")
            self.panel.pinned.update(self.panel.lines)
            missing = []
            if record.get('kind', 'continuous') == 'continuous':
                target = record.get('checkpoint_start', 1_000_000)
                observed = {r['requested'] for r in self.records}
                highest = max((r['actual'] for r in self.records), default=0)
                ceiling = record.get('checkpoint_maximum') or highest
                while target <= min(highest,ceiling):
                    if target not in observed: missing.append(node_label(target))
                    target *= 2
            best = record['lines'].get('1', {})
            depths = {line.get('depth') for line in record['lines'].values()}
            freshness = 'Mixed-depth ranks; not synchronized' if len(depths) > 1 else 'Observed ranks; per-line node counts may differ'
            self.details.setText(f"{freshness} · Not recorded: {', '.join(missing) or 'none between recorded bounds'}\n{record['profile']['name']}\n"
                f"Depth {best.get('depth', 0)} / seldepth {best.get('seldepth', 0)} · "
                f"{best.get('seconds', 0):g}s · {best.get('nps', 0):,} nps\n"
                f"{'FINAL RESULT · ' if record.get('final') else ''}{record.get('kind', 'continuous')} search · {'complete ranks' if record['complete'] else 'INCOMPLETE ranks'}\n"
                'Scores use selected perspective; ranks may have different depths/nodes (hover a line for statistics).')
        else:
            self.details.setText('Missing analysis. Queue an explicit supplementary search below.')
        if self.record:self.details.setToolTip(self.record['fen'])
        self.selected.emit()


class Evolution(QWidget):
    point_selected = Signal(int, object)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(220)
        self.series = [[], []]
        self.enabled = [True, True]
        self.points = []
        self.metric = 'evaluation'
        self.setMouseTracking(True)

    def mouseMoveEvent(self,event):
        from PySide6.QtWidgets import QToolTip
        if self.points:
            point,side,record=min(self.points,key=lambda item:(item[0]-event.position()).manhattanLength())
            if (point-event.position()).manhattanLength()<25:
                QToolTip.showText(event.globalPosition().toPoint(),f"Engine {'AB'[side]} · target {record['requested']:,} · actual {record['actual']:,} · {record['lines'].get('1',{})}",self)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#1b2028'))
        p.setPen(QColor('#bfc8ce'))
        p.drawText(12, 20, ('Depth' if self.metric == 'depth' else 'Evaluation (White cp)')+' / log₂ checkpoint · click a point')
        rows = [r for series in self.series for r in series]
        if not rows:
            p.drawText(12, 65, 'Stored search history will appear here. Mate/missing/bound scores are excluded.')
            return
        lo = min(math.log2(r['requested']) for r in rows)
        hi = max(math.log2(r['requested']) for r in rows)
        self.points = []
        for side, series in enumerate(self.series):
            if not self.enabled[side]:
                continue
            p.setPen(QPen(QColor('#6cbeb7' if side == 0 else '#d9ad71'), 2))
            previous = None
            # One search at a time: never join unrelated searches with a line.
            previous_id = None
            for r in sorted(series, key=lambda r: (r['timestamp'], r['requested'])):
                line = r['lines'].get('1', {})
                if self.metric != 'depth' and (line.get('score_type') != 'cp' or line.get('bound', 'exact') != 'exact'):
                    previous = None
                    continue
                x = 35 + (math.log2(r['requested'])-lo)/max(1, hi-lo)*(self.width()-70)
                perspective = 1 if r['fen'].split()[1] == 'w' else -1
                value = line.get('depth',0)*4 if self.metric == 'depth' else line['score_value'] * perspective
                y = self.height()/2 - max(-500, min(500, value))/500*(self.height()/2-45)
                from PySide6.QtCore import QPointF
                point = QPointF(x, y)
                if previous is not None and previous_id == r['id']:
                    p.drawLine(previous, point)
                p.drawEllipse(point, 4, 4)
                self.points.append((point, side, r))
                previous, previous_id = point, r['id']
        p.setPen(QColor('#88939d'))
        p.drawText(12, self.height()-8, f"{node_label(min(r['requested'] for r in rows))} → "
            f"{node_label(max(r['requested'] for r in rows))}; graph clipped at ±5 pawns")

    def mousePressEvent(self, event):
        if self.points:
            point, side, record = min(self.points, key=lambda item: (item[0]-event.position()).manhattanLength())
            if (point-event.position()).manhattanLength() < 30:
                self.point_selected.emit(side, record)


