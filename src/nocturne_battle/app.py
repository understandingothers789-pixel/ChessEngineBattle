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
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, QPlainTextEdit)
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
from .runtime import Search, Tournament


def button(text, callback, layout):
    control = QPushButton(text)
    control.clicked.connect(callback)
    layout.addWidget(control)
    return control


class ProfileDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle('Engine profile · validate a local UCI executable')
        self.resize(650, 520)
        self.profile = None
        self.discovered = None
        self.connection = UciConnection(self)
        self.connection.discovered.connect(self.discover)
        self.connection.failed.connect(self.error)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.name = QLineEdit(existing.name if existing else '')
        self.path = QLineEdit(existing.path if existing else '')
        self.args = QLineEdit(json.dumps(existing.arguments if existing else []))
        self.options = QPlainTextEdit(json.dumps(existing.options if existing else {'Threads': 1, 'Hash': 64}, indent=2))
        form.addRow('Profile name', self.name)
        form.addRow('Executable', self.path)
        button('Browse executable…', self.browse, layout)
        form.addRow('Arguments (JSON array)', self.args)
        form.addRow('UCI options (JSON object)', self.options)
        self.status = QLabel('Validate to discover the engine and its supported options.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        button('Validate engine / discover options', self.validate, layout)
        self.option_list = QPlainTextEdit()
        self.option_list.setReadOnly(True)
        layout.addWidget(self.option_list)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.save)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

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
        self.status.setText('Validated: ' + data['name'])
        self.option_list.setPlainText('\n'.join(f'{o.name}: {o.kind}, default={o.default}, '
            f'range={o.minimum}–{o.maximum}, choices={o.choices}' for o in data['options'].values()))

    def save(self):
        try:
            if not self.discovered or self.validation != (self.path.text(), self.args.text()):
                raise ValueError('Validate this executable and arguments before saving')
            if not self.name.text().strip():
                raise ValueError('Enter a profile name')
            options = json.loads(self.options.toPlainText())
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
        layout.addWidget(QLabel(title))
        self.checkpoint = QComboBox()
        self.checkpoint.currentIndexChanged.connect(self.choose)
        layout.addWidget(self.checkpoint)
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
        pin.toggled.connect(self.pin)
        layout.addWidget(pin)

    def pin(self, value):
        self.pinned = value
        if not value:
            self.preview_end.emit()

    def load(self, records, turn):
        sid = (self.record['id'], self.record['requested']) if self.record else None
        self.records = records
        self.turn = turn
        self.checkpoint.blockSignals(True)
        self.checkpoint.clear()
        for record in records:
            self.checkpoint.addItem(f"{node_label(record['requested'])} → {node_label(record['actual'])} actual · "
                f"{record['provenance']} · PV{record['multipv']} · {record['status']}")
        selected = next((i for i, r in enumerate(records) if (r['id'], r['requested']) == sid), len(records)-1)
        self.checkpoint.setCurrentIndex(selected)
        self.checkpoint.blockSignals(False)
        self.choose()

    def choose(self):
        index = self.checkpoint.currentIndex()
        self.record = self.records[index] if 0 <= index < len(self.records) else None
        self.panel.clear()
        if self.record:
            record = self.record
            self.panel.set_multipv(record['multipv'])
            for line in record['lines'].values():
                self.panel.update_line(line, self.turn)
                rank = line['multipv']
                if rank in self.panel.rows:
                    self.panel.rows[rank][2].setToolTip(
                        f"Reported {line.get('nodes', 0):,} nodes · {line.get('nps', 0):,} nps · "
                        f"{line.get('seconds', 0):g}s · depth {line.get('depth', 0)} / seldepth {line.get('seldepth', 0)}")
            self.panel.pinned.update(self.panel.lines)
            best = record['lines'].get('1', {})
            self.details.setText(f"{record['profile']['name']} · {record['fen']}\n"
                f"Depth {best.get('depth', 0)} / seldepth {best.get('seldepth', 0)} · "
                f"{best.get('seconds', 0):g}s · {best.get('nps', 0):,} nps\n"
                f"Continuous-search observation · {'complete ranks' if record['complete'] else 'INCOMPLETE ranks'}\n"
                'Scores use selected perspective; ranks may have different depths/nodes (hover a line for statistics).')
        else:
            self.details.setText('Missing analysis. Queue an explicit supplementary search below.')
        self.selected.emit()


class Evolution(QWidget):
    point_selected = Signal(int, object)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(220)
        self.series = [[], []]
        self.enabled = [True, True]
        self.points = []

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#1b2028'))
        p.setPen(QColor('#bfc8ce'))
        p.drawText(12, 20, 'Evaluation (White cp) / log₂ reported checkpoint · click a point')
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
                if line.get('score_type') != 'cp' or line.get('bound', 'exact') != 'exact':
                    previous = None
                    continue
                x = 35 + (math.log2(r['requested'])-lo)/max(1, hi-lo)*(self.width()-70)
                perspective = 1 if r['fen'].split()[1] == 'w' else -1
                value = line['score_value'] * perspective
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


class Window(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._closed = False
        db.recover()
        self.setWindowTitle('Nocturne · Engine Match & Analysis Studio')
        self.resize(1800, 1000)
        self.profiles = [Profile(**p) for p in db.get('profiles', [])]
        self.tournament = Tournament(db, self)
        self.tournament.changed.connect(self.match_changed)
        self.tournament.failed.connect(self.error)
        self.tournament.search.updated.connect(self.live_info)
        self.analysis = Search(db, self)
        self.analysis.completed.connect(self.analysis_complete)
        self.analysis.failed.connect(self.analysis_error)
        self.queue = []
        self.view_game = Game()
        self.follow_live = True
        self.syncing = False
        self.preview_owner = None
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        title = QLabel('NOCTURNE  /  ENGINE MATCH & ANALYSIS')
        title.setStyleSheet('font-size: 22px; padding: 12px;')
        outer.addWidget(title)
        self.splitter = QSplitter()
        outer.addWidget(self.splitter)
        board_area = QWidget()
        board_layout = QVBoxLayout(board_area)
        self.position_label = QLabel('Game position')
        board_layout.addWidget(self.position_label)
        board_row = QHBoxLayout()
        self.board = BoardWidget()
        self.board.interactive = False
        self.evalbar = EvaluationBar()
        self.evalbar.board_view = self.board
        board_row.addWidget(self.board, 1)
        board_row.addWidget(self.evalbar)
        board_layout.addLayout(board_row, 1)
        nav = QHBoxLayout()
        button('⏮', lambda: self.navigate(0), nav)
        button('←', lambda: self.navigate(self.view_game.cursor-1), nav)
        button('→', lambda: self.navigate(self.view_game.cursor+1), nav)
        button('⏭', lambda: self.navigate(len(self.view_game.moves)), nav)
        button('Flip', self.flip, nav)
        button('Return to Live', self.return_live, nav)
        board_layout.addLayout(nav)
        self.game_selector = QComboBox()
        self.game_selector.currentIndexChanged.connect(self.select_game)
        board_layout.addWidget(self.game_selector)
        self.moves = QPlainTextEdit()
        self.moves.setReadOnly(True)
        self.moves.setMaximumHeight(100)
        board_layout.addWidget(self.moves)
        self.splitter.addWidget(board_area)
        work = QWidget()
        work_layout = QVBoxLayout(work)
        row = QHBoxLayout()
        self.link = QComboBox()
        self.link.addItems(['Independent checkpoints', 'Synchronize checkpoints', 'Lock node ratio'])
        self.ratio = QComboBox()
        self.ratio.setEditable(True)
        self.ratio.addItems(['1', '2', '5', '10', '25', '50', '100'])
        self.perspective = QComboBox()
        self.perspective.addItems(["White perspective", "Side to move perspective"])
        self.perspective.currentIndexChanged.connect(self.refresh_analysis)
        row.addWidget(self.perspective)
        self.dual = QCheckBox('Dual boards')
        self.dual.toggled.connect(self.dual_mode)
        row.addWidget(self.link)
        row.addWidget(self.ratio)
        row.addWidget(self.dual)
        work_layout.addLayout(row)
        self.tabs = QTabWidget()
        self.panels = [AnalysisPanel('ENGINE A'), AnalysisPanel('ENGINE B')]
        panels_widget = QSplitter()
        for side, panel in enumerate(self.panels):
            panels_widget.addWidget(panel)
            panel.selected.connect(lambda s=side: self.selection_changed(s))
            panel.preview.connect(lambda rank, ply, s=side: self.preview(s, rank, ply))
            panel.preview_end.connect(lambda s=side: self.end_preview(s))
        self.tabs.addTab(panels_widget, 'Search comparison')
        evolution_area = QWidget()
        evo_layout = QVBoxLayout(evolution_area)
        self.graph = Evolution()
        self.graph.point_selected.connect(self.graph_select)
        evo_layout.addWidget(self.graph)
        series_row = QHBoxLayout()
        for side in range(2):
            toggle = QCheckBox(f'Engine {"AB"[side]}')
            toggle.setChecked(True)
            toggle.toggled.connect(lambda checked, s=side: self.toggle_series(s, checked))
            series_row.addWidget(toggle)
        evo_layout.addLayout(series_row)
        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(['Engine', 'Target → actual', 'Best move', 'Evaluation (White)', 'Provenance'])
        self.history.cellClicked.connect(self.history_select)
        evo_layout.addWidget(self.history)
        self.tabs.addTab(evolution_area, 'Search evolution')
        self.stats = QPlainTextEdit()
        self.stats.setReadOnly(True)
        self.tabs.addTab(self.stats, 'Results')
        work_layout.addWidget(self.tabs, 1)
        self.comparison = QLabel('Compare This Position to retrieve exact-position history.')
        self.comparison.setWordWrap(True)
        work_layout.addWidget(self.comparison)
        self.splitter.addWidget(work)
        config_area = QWidget()
        config = QVBoxLayout(config_area)
        config.addWidget(QLabel('MATCH SETUP'))
        form = QFormLayout()
        config.addLayout(form)
        self.engines = [QComboBox(), QComboBox()]
        form.addRow('Engine A', self.engines[0])
        form.addRow('Engine B', self.engines[1])
        button('Add / clone engine profile…', self.add_profile, config)
        self.mode = QComboBox()
        self.mode.addItems(['nodes', 'depth', 'movetime'])
        self.budgets = [QLineEdit('100000000'), QLineEdit('1000000000')]
        form.addRow('Search mode', self.mode)
        form.addRow('A limit', self.budgets[0])
        form.addRow('B limit', self.budgets[1])
        button('Apply B:A node ratio', self.apply_ratio, config)
        self.book = QLineEdit()
        form.addRow('Opening suite', self.book)
        button('Choose / validate PGN or EPD…', self.choose_book, config)
        self.pairs = QSpinBox()
        self.pairs.setRange(1, 100000)
        self.pairs.setValue(100)
        form.addRow('Opening pairs', self.pairs)
        self.play_pv = QSpinBox()
        self.play_pv.setRange(1, 5)
        form.addRow('Playing MultiPV', self.play_pv)
        self.checkpoint = QLineEdit('1000000')
        form.addRow('First checkpoint', self.checkpoint)
        button('Start new match', self.start_match, config)
        button('Pause match', self.tournament.pause, config)
        button('Resume persisted match', self.resume, config)
        advanced = QGroupBox('Advanced settings')
        advanced.setCheckable(True)
        advanced.setChecked(False)
        adv_layout = QVBoxLayout(advanced)
        adv_body = QWidget()
        adv_form = QFormLayout(adv_body)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.randomized = QCheckBox('Randomize openings')
        self.maximum = QLineEdit('')
        adv_form.addRow('Seed', self.seed)
        adv_form.addRow(self.randomized)
        adv_form.addRow('Maximum checkpoint (blank: unlimited)', self.maximum)
        adv_layout.addWidget(adv_body)
        adv_body.hide()
        advanced.toggled.connect(adv_body.setVisible)
        config.addWidget(advanced)
        config.addWidget(QLabel('POSITION ANALYSIS'))
        button('Compare This Position', self.refresh_analysis, config)
        self.supp_pv = QSpinBox()
        self.supp_pv.setRange(1, 5)
        self.supp_pv.setValue(5)
        config.addWidget(QLabel('Supplementary MultiPV (separate searches)'))
        config.addWidget(self.supp_pv)
        button('Queue A + B supplementary searches', self.queue_analysis, config)
        button('Cancel analysis queue', self.cancel_analysis, config)
        queue_note = QLabel('Supplementary jobs run only while match is paused. Limits above apply; no expensive searches start automatically.')
        queue_note.setWordWrap(True)
        config.addWidget(queue_note)
        button('Export JSON / CSV / PGN…', self.export, config)
        config.addStretch()
        self.status = QLabel('Ready · add your UCI engines. No engines bundled.')
        self.status.setWordWrap(True)
        config.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(config_area)
        scroll.setMinimumWidth(290)
        self.splitter.addWidget(scroll)
        self.splitter.setSizes([600, 850, 330])
        self.populate_profiles()
        self.restore_settings()
        self.board.wheel_navigated.connect(lambda delta: self.navigate(self.view_game.cursor+delta))
        for key, callback in [('Left', lambda: self.navigate(self.view_game.cursor-1)),
                              ('Right', lambda: self.navigate(self.view_game.cursor+1))]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        self.match_changed()

    def error(self, text):
        self.status.setText(text)
        QMessageBox.warning(self, 'Nocturne Battle', text)

    def populate_profiles(self):
        for control in self.engines:
            index = control.currentIndex()
            control.clear()
            control.addItems([p.name for p in self.profiles])
            control.setCurrentIndex(max(0, index))

    def add_profile(self):
        source = self.profiles[self.engines[0].currentIndex()] if self.profiles else None
        dialog = ProfileDialog(self, source)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.profiles.append(dialog.profile)
            self.db.put('profiles', [asdict(p) for p in self.profiles])
            self.populate_profiles()
            self.engines[1].setCurrentIndex(len(self.profiles)-1)

    def selected_profiles(self):
        if not self.profiles:
            raise ValueError('Add and validate UCI engine profiles first')
        return [self.profiles[c.currentIndex()] for c in self.engines]

    def limits(self):
        mode = self.mode.currentText()
        result = [Limit(mode, int(c.text()) if mode != 'movetime' else float(c.text())) for c in self.budgets]
        for limit in result:
            limit.validate()
        return result

    def bounds(self):
        from .history import Checkpoints
        start = int(self.checkpoint.text())
        maximum = int(self.maximum.text()) if self.maximum.text().strip() else None
        Checkpoints(start, maximum)
        return start, maximum

    def apply_ratio(self):
        try:
            if self.mode.currentText() != 'nodes':
                raise ValueError('Node ratios require fixed nodes mode')
            from decimal import Decimal
            value = Decimal(self.budgets[0].text()) * Decimal(self.ratio.currentText())
            if value <= 0 or value != int(value):
                raise ValueError('Ratio must produce a positive integer node budget')
            self.budgets[1].setText(str(int(value)))
        except Exception as exc:
            self.error(str(exc))

    def choose_book(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose opening suite', filter='Opening suites (*.pgn *.epd)')
        if path:
            try:
                fens = openings(path)
                self.book.setText(path)
                self.status.setText(f'Validated {len(fens)} opening positions. First: {fens[0]}')
            except (ValueError, OSError) as exc:
                self.error(str(exc))

    def start_match(self):
        try:
            profiles, limits = self.selected_profiles(), self.limits()
            start, maximum = self.bounds()
            if self.tournament.state:
                old = self.tournament.state
                self.db.put('tournament:'+old['id'], old)
            self.cancel_analysis()
            self.tournament.create(profiles, limits, schedule(openings(self.book.text()),
                self.pairs.value(), self.seed.value(), self.randomized.isChecked()),
                self.play_pv.value(), start, maximum, self.seed.value())
            self.follow_live = True
            self.save_settings()
            self.tournament.resume()
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def resume(self):
        self.cancel_analysis()
        self.tournament.resume()

    def match_changed(self):
        state = self.tournament.state
        if not state:
            self.show_game()
            return
        self.game_selector.blockSignals(True)
        current = self.game_selector.currentIndex()
        self.game_selector.clear()
        self.game_selector.addItems([f"Game {i+1} · Pair {g['pair']+1} · A {'White' if g['a_white'] else 'Black'} · {g['result']}"
                                     for i, g in enumerate(state['games'])])
        index = min(state['index'], len(state['games'])-1) if self.follow_live else max(0, current)
        self.game_selector.setCurrentIndex(index)
        self.game_selector.blockSignals(False)
        if self.follow_live:
            self.load_game(index)
        results = state['games']
        wins = sum((g['result']=='1-0' and g['a_white']) or (g['result']=='0-1' and not g['a_white']) for g in results)
        losses = sum((g['result']=='0-1' and g['a_white']) or (g['result']=='1-0' and not g['a_white']) for g in results)
        draws = sum(g['result']=='1/2-1/2' for g in results)
        n = wins+losses+draws
        self.stats.setPlainText(f'A wins: {wins}\nB wins: {losses}\nDraws: {draws}\nCompleted: {n}/{len(results)}\n'
            f"A score: {(wins+draws/2)/n:.1%}" if n else 'No completed games. Elo estimates require more evidence.')
        self.status.setText(f"{'Running' if self.tournament.active else 'Paused / complete'} · game {index+1}/{len(results)}")

    def live_info(self, info):
        game = self.tournament.game
        if not self.follow_live or not game or not self.tournament.active:
            return
        item = self.tournament.state['games'][self.tournament.state['index']]
        side = 0 if ((game.board.turn == 1) == item['a_white']) else 1
        panel = self.panels[side]
        if panel.record is None:
            panel.panel.set_multipv(self.tournament.state['multipv'])
            panel.panel.update_line(info, game.board.turn if self.perspective.currentIndex() == 0 else 1)
            panel.details.setText(f"Live playing search · Engine {'AB'[side]} · "
                f"{info.get('nodes', 0):,} nodes · depth {info.get('depth', 0)} / "
                f"seldepth {info.get('seldepth', 0)} · {info.get('seconds', 0):g}s · "
                f"{info.get('nps', 0):,} nps")
            self.evalbar.set_score(info.get('score', 0)*game.board.turn)
        self.status.setText(f"Playing · Engine {'AB'[side]} · {info.get('nodes', 0):,} reported nodes")

    def load_game(self, index):
        state = self.tournament.state
        item = state['games'][index]
        self.view_game = Game(item['fen'])
        self.view_game.id = item.get('id', self.view_game.id)
        for uci in item['moves']:
            self.view_game.play(self.view_game.board.parse_uci(uci))
        self.show_game()

    def select_game(self, index):
        if self.tournament.state and index >= 0:
            self.follow_live = False
            self.load_game(index)

    def navigate(self, cursor):
        self.follow_live = False
        self.view_game.navigate(max(0, min(len(self.view_game.moves), cursor)))
        self.show_game()

    def return_live(self):
        self.follow_live = True
        self.match_changed()

    def show_game(self):
        game = self.view_game
        last = game.moves[game.cursor-1] if game.cursor else None
        self.board.set_position(game.board.copy(), last)
        self.position_label.setText(f"{'Live' if self.follow_live else 'Historical'} · ply {game.cursor} · "
                                    f"{'White' if game.board.turn == 1 else 'Black'} to move")
        self.moves.setPlainText(' '.join(f'{i//2+1}. {s}' if i%2==0 else s for i, s in enumerate(game.sans)))
        for panel in self.panels:
            panel.pinned = False
            panel.board.set_position(game.board.copy(), last)
        self.refresh_analysis()

    def flip(self):
        self.board.flip()
        self.evalbar.flipped = self.board.flipped
        self.evalbar.update()
        for panel in self.panels:
            panel.board.flip()

    def refresh_analysis(self):
        if not self.profiles:
            return
        self.syncing = True
        for panel, profile in zip(self.panels, self.selected_profiles()):
            panel.load(self.db.records(self.view_game, profile), self.view_game.board.turn if self.perspective.currentIndex() == 0 else 1)
        self.syncing = False
        self.selection_changed(0)
        self.graph.series = [panel.records for panel in self.panels]
        self.graph.update()
        self.history_rows = [(side, record) for side, panel in enumerate(self.panels) for record in panel.records]
        self.history.setRowCount(len(self.history_rows))
        for row, (side, record) in enumerate(self.history_rows):
            line = record['lines'].get('1', {})
            perspective = 1 if record['fen'].split()[1] == 'w' else -1
            values = ['AB'[side], f"{node_label(record['requested'])} → {node_label(record['actual'])}",
                      ' '.join(line.get('san', [])[:1]), score_label(line, perspective) if line else 'Missing', record['provenance']]
            for col, value in enumerate(values):
                self.history.setItem(row, col, QTableWidgetItem(value))

    def selection_changed(self, side):
        if self.syncing:
            return
        self.syncing = True
        label = ''
        source, target = self.panels[side], self.panels[1-side]
        try:
            if self.link.currentIndex() and source.record:
                ratio = float(self.ratio.currentText()) if self.link.currentIndex() == 2 else 1
                if not math.isfinite(ratio) or ratio <= 0:
                    raise ValueError('Choose a finite positive ratio')
                requested = source.record['requested'] * (ratio if side == 0 else 1/ratio)
                record, accuracy = select_checkpoint(target.records, requested)
                label = f'Linked target {requested:g} nodes: {accuracy}. '
                if record:
                    target.checkpoint.setCurrentIndex(target.records.index(record))
            a, b = [p.record for p in self.panels]
            result = compare(a, b, self.panels[0].pv_rank.value(), self.panels[1].pv_rank.value())
            self.comparison.setText(label + result['status'] +
                (f" · overlap (move, A rank, B rank): {result.get('overlap')}\n"
                 f"Unique A: {result.get('only_a')} · Unique B: {result.get('only_b')} · "
                 f"Shared PV prefix: {result.get('shared_prefix')} plies · divergence: {result.get('divergence')}"
                 if 'overlap' in result else ''))
            line = a['lines'].get('1', {}) if a else {}
            self.evalbar.set_score(line.get('score', 0)*self.view_game.board.turn if line else None)
        except ValueError as exc:
            self.comparison.setText(str(exc))
        finally:
            self.syncing = False

    def preview(self, side, rank, ply):
        panel = self.panels[side]
        if panel.pinned:
            return
        info = panel.panel.lines.get(rank)
        if not info:
            return
        board = self.view_game.board.copy()
        last = None
        for uci in info['pv'][:ply]:
            last = board.parse_uci(uci)
            board.push(last)
        target = panel.board if self.dual.isChecked() else self.board
        if target is self.board and any(p.pinned for p in self.panels):
            return
        self.preview_owner = side
        target.show_preview(board, last, f'Engine {"AB"[side]} · PV{rank} · ply {ply}')

    def end_preview(self, side):
        if self.panels[side].pinned:
            return
        self.panels[side].board.clear_preview()
        if self.preview_owner == side:
            self.board.clear_preview()
            self.preview_owner = None

    def dual_mode(self, enabled):
        self.board.clear_preview()
        for panel in self.panels:
            panel.board.setVisible(enabled)

    def queue_analysis(self):
        try:
            if self.tournament.active:
                raise ValueError('Pause the match before allocating engines to supplementary work')
            if self.analysis.context:
                raise ValueError('Wait for the current queue or cancel it')
            profiles, limits = self.selected_profiles(), self.limits()
            start, maximum = self.bounds()
            game = Game.from_dict(self.view_game.to_dict())
            state = self.tournament.state
            index = self.game_selector.currentIndex()
            provenance = ('supplementary-during-match' if state and index >= 0 and
                          state['games'][index]['result'] == '*' else 'post-game')
            self.queue.extend((game, p, limit, self.supp_pv.value(), start, maximum, provenance)
                              for p, limit in zip(profiles, limits))
            self.run_next()
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def run_next(self):
        if self.queue:
            game, profile, limit, pv, start, maximum, provenance = self.queue.pop(0)
            try:
                self.status.setText('Supplementary analysis: ' + profile.name)
                self.analysis.start(game, profile, limit, pv, provenance, start, maximum)
            except (ValueError, OSError) as exc:
                self.analysis_error(str(exc))
        else:
            self.status.setText('Analysis queue complete · history persisted')

    def analysis_complete(self, data):
        self.refresh_analysis()
        self.run_next()

    def analysis_error(self, text):
        self.cancel_analysis()
        self.error(text)

    def cancel_analysis(self):
        self.queue.clear()
        self.analysis.cancel()

    def graph_select(self, side, record):
        self.panels[side].checkpoint.setCurrentIndex(self.panels[side].records.index(record))
        self.tabs.setCurrentIndex(0)

    def history_select(self, row, col):
        self.graph_select(*self.history_rows[row])

    def toggle_series(self, side, checked):
        self.graph.enabled[side] = checked
        self.graph.update()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export match and analysis', filter='JSON (*.json);;CSV (*.csv);;PGN (*.pgn)')
        if not path:
            return
        try:
            suffix = Path(path).suffix.lower()
            if suffix == '.json':
                Path(path).write_text(json.dumps(self.db.export(), indent=2), encoding='utf-8')
            elif suffix == '.csv':
                with open(path, 'w', newline='', encoding='utf-8') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['search', 'position', 'engine', 'provenance', 'target', 'actual', 'rank', 'line_json'])
                    for record in self.db.export()['snapshots']:
                        for rank, line in record['lines'].items():
                            writer.writerow([record['id'], record['position'], record['profile']['name'],
                                record['provenance'], record['requested'], record['actual'], rank, json.dumps(line)])
            elif suffix == '.pgn':
                texts = []
                if self.tournament.state:
                    state = self.tournament.state
                    for item in state['games']:
                        game = Game(item['fen'])
                        for uci in item['moves']:
                            game.play(game.board.parse_uci(uci))
                        white = 0 if item['a_white'] else 1
                        game.headers.update(White=state['profiles'][white]['name'], Black=state['profiles'][1-white]['name'],
                                            Result=item['result'], Event='Nocturne Battle', Seed=str(state['seed']),
                                            BattleConfig=json.dumps({k:v for k,v in state.items() if k != 'games'}))
                        texts.append(game.pgn())
                Path(path).write_text('\n\n'.join(texts), encoding='utf-8')
            else:
                raise ValueError('Choose .json, .csv or .pgn')
            self.status.setText('Exported ' + path)
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def save_settings(self):
        self.db.put('workspace', dict(splitter=self.splitter.sizes(), mode=self.mode.currentText(),
            budgets=[x.text() for x in self.budgets], engines=[x.currentIndex() for x in self.engines],
            book=self.book.text(), pairs=self.pairs.value(), play_pv=self.play_pv.value(),
            checkpoint=self.checkpoint.text(), maximum=self.maximum.text(), seed=self.seed.value(),
            randomized=self.randomized.isChecked(), ratio=self.ratio.currentText(), dual=self.dual.isChecked()))

    def restore_settings(self):
        state = self.db.get('workspace')
        if not state:
            return
        self.splitter.setSizes(state['splitter'])
        self.mode.setCurrentText(state['mode'])
        for control, value in zip(self.budgets, state['budgets']):
            control.setText(value)
        for control, index in zip(self.engines, state['engines']):
            control.setCurrentIndex(min(index, len(self.profiles)-1))
        self.book.setText(state['book'])
        self.pairs.setValue(state['pairs'])
        self.play_pv.setValue(state['play_pv'])
        self.checkpoint.setText(state['checkpoint'])
        self.maximum.setText(state['maximum'])
        self.seed.setValue(state['seed'])
        self.randomized.setChecked(state['randomized'])
        self.ratio.setCurrentText(state['ratio'])
        self.dual.setChecked(state['dual'])

    def closeEvent(self, event):
        if self._closed:
            event.accept()
            return
        self._closed = True
        self.save_settings()
        if self.tournament.state:
            self.tournament.pause()
        self.tournament.search.close()
        self.analysis.close()
        self.db.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('NocturneBattle')
    app.setOrganizationName('Nocturne')
    app.setStyleSheet(stylesheet())
    directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    window = Window(Database(directory / 'battle.sqlite'))
    window.show()
    if '--smoke-test' in sys.argv:
        def smoke():
            success = not window.grab().isNull() and window.board.isVisible()
            window.close()
            app.exit(0 if success else 1)
        QTimer.singleShot(250, smoke)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
