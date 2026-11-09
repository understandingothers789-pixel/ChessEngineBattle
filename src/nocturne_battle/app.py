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
    QFormLayout, QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QSplitter, QScrollArea, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, QPlainTextEdit, QTextBrowser, QListWidget,QListWidgetItem)
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
from .time_editor import MinutesSeconds
from .game_browser import GameBrowser
from .experiments import ExperimentRunner
from .experiment_ui import ScalingPanel
from .comparison_ui import CandidateViews
from .model import parse_budget


def button(text, callback, layout):
    control = QPushButton(text)
    control.clicked.connect(callback)
    layout.addWidget(control)
    return control


from .widgets import ProfileDialog, AnalysisPanel, Evolution


class Window(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._closed = False
        db.recover()
        self.setWindowTitle('Nocturne Battle 0.3.6 · Engine Match & Analysis Studio')
        self.resize(1800, 1000)
        self.profiles = [Profile(**p) for p in db.get('profiles', [])]
        self.tournament = Tournament(db, self)
        self.tournament.changed.connect(self.match_changed)
        self.tournament.failed.connect(self.error)
        self.tournament.clock_changed.connect(self.update_clocks)
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
        quick = QHBoxLayout()
        self.load_a_button = button('Open engine file for A…', lambda:self.load_engine(0), quick)
        self.load_b_button = button('Open engine file for B…', lambda:self.load_engine(1), quick)
        button('Match setup',lambda:self.workspace.setCurrentIndex(0),quick)
        outer.addLayout(quick)
        self.workspace = QComboBox()
        self.workspace.addItems(['Match Setup', 'Live Match', 'Analysis Comparison', 'Results & History', 'Node Scaling Experiment'])
        outer.addWidget(self.workspace)

        self.splitter = QSplitter()
        outer.addWidget(self.splitter)
        board_area = QWidget()
        board_layout = QVBoxLayout(board_area)
        self.position_label = QLabel('Game position')
        board_layout.addWidget(self.position_label)
        self.clock_label=QLabel('')
        self.clock_label.setToolTip('Live game clocks. Preparation is excluded; each accepted move earns its increment. Pausing freezes the remaining time.')
        self.clock_label.setStyleSheet('font-size: 19px; padding: 6px;')
        board_layout.addWidget(self.clock_label)
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
        button('Original thinking', self.original_thinking, board_layout)
        board_layout.addLayout(nav)
        self.game_selector = QComboBox()
        self.game_selector.currentIndexChanged.connect(self.select_game)
        self.game_selector.hide()
        self.game_filter = QLineEdit()
        self.game_filter.setPlaceholderText('Filter games by engine, pair, result or status')
        self.game_filter.textChanged.connect(self.filter_games)
        board_layout.addWidget(self.game_filter)
        self.games_table = GameBrowser()
        self.games_table.setMaximumHeight(180)
        self.games_table.clicked.connect(lambda index:self.table_game(index.row(),index.column()))
        board_layout.addWidget(self.games_table)
        self.moves = QTextBrowser()
        self.moves.setOpenLinks(False)
        self.moves.anchorClicked.connect(lambda url: self.navigate(int(url.toString())))
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
        compact=QCheckBox('Compact')
        compact.toggled.connect(lambda enabled:[p.details.setVisible(not enabled) for p in self.panels])
        row.addWidget(compact)
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
        metric=QComboBox();metric.addItems(['Evaluation','Depth'])
        metric.currentIndexChanged.connect(lambda index:(setattr(self.graph,'metric','depth' if index else 'evaluation'),self.graph.update()))
        evo_layout.addWidget(metric)
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
        self.discovery = QListWidget();self.discovery.setMaximumHeight(130)
        self.discovery.itemActivated.connect(self.milestone_clicked)
        evo_layout.addWidget(self.discovery)
        self.tabs.addTab(evolution_area, 'Search evolution')
        self.stats = QPlainTextEdit()
        self.stats.setReadOnly(True)
        library = QWidget()
        library_layout = QVBoxLayout(library)
        self.archive_selector = QComboBox()
        self.archive_selector.addItem('Select a saved tournament…', None)
        for state in db.archives():
            self.archive_selector.addItem(f"{state['id'][:8]} · {len(state['games'])} games · {state['index']} completed", state['id'])
        library_layout.addWidget(self.archive_selector)
        button('Open selected tournament', self.open_archive, library_layout)
        library_layout.addWidget(self.stats)
        self.tabs.addTab(library, 'Results & History')
        live = QWidget()
        live_layout = QVBoxLayout(live)
        self.live_panels = []
        self.live_labels = []
        self.live_positions = [None,None]
        for side in range(2):
            panel = CandidatePanel(MoveText(auto_fit=True))
            panel.set_maia(enabled=False)
            label = QLabel('Live engine '+ 'AB'[side]); label.setWordWrap(True)
            self.live_labels.append(label); live_layout.addWidget(label)
            live_layout.addWidget(panel)
            self.live_panels.append(panel)
        self.tabs.addTab(live, 'Live Match')
        self.candidate_views = CandidateViews()
        self.candidate_views.inspect.connect(self.inspect_candidate)
        self.tabs.addTab(self.candidate_views, 'Candidate rankings')
        self.experiment = ExperimentRunner(db,self.tournament)
        self.scaling = ScalingPanel(self,self.experiment)
        self.tabs.addTab(self.scaling, 'Node Scaling Experiment')


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
        self.limit_form=form
        self.engines = [QComboBox(), QComboBox()]
        form.addRow('Engine A', self.engines[0])
        form.addRow('Engine B', self.engines[1])
        management=QGroupBox('Manage saved engines (optional)')
        management.setCheckable(True);management.setChecked(False)
        management_layout=QVBoxLayout(management);management_body=QWidget()
        management_buttons=QVBoxLayout(management_body)
        button('Duplicate selected engine settings…',self.add_profile,management_buttons)
        button('Edit selected A profile…',self.edit_profile,management_buttons)
        button('Remove selected A profile',self.remove_profile,management_buttons)
        button('Unload Engine A',lambda:self.unload_engine(0),management_buttons)
        button('Unload Engine B',lambda:self.unload_engine(1),management_buttons)
        management_layout.addWidget(management_body);management_body.hide()
        management.toggled.connect(management_body.setVisible);config.addWidget(management)
        self.welcome = QLabel('Start here: click Open engine file for A above and choose your engine’s .exe file. Test it, then save. You can use the same engine for both sides. No engines are included.')
        self.welcome.setWordWrap(True); self.welcome.setVisible(not self.profiles)
        config.insertWidget(1,self.welcome)

        self.mode = QComboBox()
        self.mode.addItems(['nodes', 'depth', 'movetime', 'clock'])
        self.mode.setItemData(3,'Base time plus an increment added after each accepted move.',Qt.ItemDataRole.ToolTipRole)
        self.budgets = [QLineEdit('100000000'), QLineEdit('1000000000')]
        form.addRow('Search mode', self.mode)
        form.addRow('Engine A search budget', self.budgets[0])
        form.addRow('Engine B search budget', self.budgets[1])
        self.clock_group=QGroupBox('Clock controls — base time + increment')
        clock_form=QFormLayout(self.clock_group)
        preset=QComboBox();preset.addItem('Apply a clock preset…',None)
        for title,minutes,increment in [('10 sec + 0.1 sec',10/60,0.1),('30 sec + 0.1 sec',0.5,0.1),('1 min + 0 sec',1,0),('3 min + 2 sec',3,2),('5 min + 3 sec',5,3),('10 min + 5 sec',10,5)]:preset.addItem(title,(minutes,increment))
        self.clock_bases=[];self.clock_increments=[]
        clock_form.addRow('Same preset for both',preset)
        for side in range(2):
            base=MinutesSeconds()
            inc=QDoubleSpinBox();inc.setRange(0,3600);inc.setDecimals(3);inc.setValue(0.1);inc.setSuffix(' sec')
            base.setToolTip('Starting time for this engine, in minutes. Each new game resets both clocks.')
            inc.setToolTip('Seconds added after each accepted move. A move received after time runs out does not earn increment.')
            self.clock_bases.append(base);self.clock_increments.append(inc)
            clock_form.addRow('Engine '+'AB'[side]+' base',base);clock_form.addRow('Engine '+'AB'[side]+' increment',inc)
        def apply_clock_preset(index):
            data=preset.itemData(index)
            if data:
                for base,inc in zip(self.clock_bases,self.clock_increments):base.setValue(data[0]);inc.setValue(data[1])
        preset.currentIndexChanged.connect(apply_clock_preset)
        self.clock_dialog=QDialog(self);self.clock_dialog.setWindowTitle('Clock controls — minutes, seconds and increment')
        clock_layout=QVBoxLayout(self.clock_dialog);clock_layout.addWidget(self.clock_group)
        done=QPushButton('Done');done.clicked.connect(self.clock_dialog.accept);clock_layout.addWidget(done)
        self.clock_button=QPushButton('Clock controls…');self.clock_button.clicked.connect(self.clock_dialog.exec)
        form.addRow(self.clock_button)
        self.clock_button.hide()
        self.mode.currentTextChanged.connect(self.search_mode_changed)

        self.ratio_button=button('Apply B:A node ratio', self.apply_ratio, config)
        self.swap_budget_button=button('Exchange A / B budgets', self.swap_budgets, config)
        self.book = QLineEdit()
        form.addRow('Opening suite', self.book)
        self.recent_books = QComboBox(); self.recent_books.addItem('Recent opening suites…')
        self.recent_books.addItems(db.get('recent_books',[]))
        self.recent_books.textActivated.connect(lambda text: self.book.setText(text) if text != 'Recent opening suites…' else None)
        form.addRow('Recent books', self.recent_books)
        bundled=QComboBox();bundled.addItem('Choose an included opening suite…','')
        for name in ('Drawkiller_balanced_big.epd','4mvs_+90_+99.epd','6mvs_+90_+99.epd'):
            path=Path(__file__).parent/'books'/name
            bundled.addItem(name+' ('+f'{path.stat().st_size/1024:.1f} KiB'+')',str(path))
        bundled.currentIndexChanged.connect(lambda index:self.book.setText(bundled.itemData(index)) if bundled.itemData(index) else None)
        form.addRow('Included opening suites',bundled)
        book_browse=QPushButton('Browse opening suite…');book_browse.clicked.connect(self.choose_book)
        form.addRow('',book_browse)
        use_book=QPushButton('Play every book opening twice');use_book.clicked.connect(self.use_full_opening_suite)
        use_book.setToolTip('Set the pair count to the number of opening entries in this book: one game per color for every entry. You can change the pair count afterward.')
        form.addRow('',use_book)
        self.pairs = QSpinBox()
        self.pairs.setRange(1, 100000)
        self.pairs.setValue(100)
        self.pairs.setToolTip('Each pair plays the same opening twice with reversed colors. 100 pairs means 200 games. The suite cycles if the number of pairs exceeds the number of book entries.')
        form.addRow('Opening pairs (2 games each)', self.pairs)
        self.pair_description=QLabel();self.pair_description.setWordWrap(True)
        self.pair_description.setToolTip('Each opening is played exactly twice with colors reversed. Total games = opening pairs × 2.')
        self.pairs.valueChanged.connect(self.update_pair_description)
        form.addRow(self.pair_description)
        self.update_pair_description()
        self.play_pv = QSpinBox()
        self.play_pv.setRange(1, 5)
        form.addRow('Playing MultiPV', self.play_pv)
        self.checkpoint = QLineEdit('1000000')
        form.addRow('First checkpoint', self.checkpoint)
        self.summary = QLabel(); self.summary.setWordWrap(True)
        config.addWidget(self.summary)
        button('Review & Start Match', self.start_match, quick)
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
        self.silence_timeout = QSpinBox();self.silence_timeout.setRange(0,3600);self.silence_timeout.setValue(120)
        adv_form.addRow('Search silence timeout (seconds; 0 disables)',self.silence_timeout)
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
        self.analysis_kind = QComboBox()
        self.analysis_kind.addItems(['Continuous history', 'Independent checkpoint searches'])
        config.addWidget(self.analysis_kind)
        button('Queue A + B supplementary searches', self.queue_analysis, config)

        button('Cancel analysis queue', self.cancel_analysis, config)
        queue_note = QLabel('Supplementary jobs run only while match is paused. Limits above apply; no expensive searches start automatically.')
        queue_note.setWordWrap(True)
        config.addWidget(queue_note)
        button('Export JSON / CSV / PGN…', self.export, config)
        config.addStretch()
        self.status = QLabel('Ready · add your UCI engines. No engines bundled.')
        self.status.setWordWrap(True)
        self.statusBar().addPermanentWidget(self.status,1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(config_area)
        scroll.setMinimumWidth(290)
        self.splitter.addWidget(scroll)
        self.splitter.setSizes([600, 850, 330])
        self.config_scroll = scroll
        self.workspace.currentIndexChanged.connect(self.change_workspace)
        self.populate_profiles()
        self.restore_settings()
        self.change_workspace(self.workspace.currentIndex())
        self.board.wheel_navigated.connect(lambda delta: self.navigate(self.view_game.cursor+delta))
        for key, callback in [('Left', lambda: self.navigate(self.view_game.cursor-1)),
                              ('Right', lambda: self.navigate(self.view_game.cursor+1))]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        self.match_changed()
        from .help import install_tooltips
        install_tooltips(self)

    def error(self, text):
        self.status.setText(text)
        QMessageBox.warning(self, 'Nocturne Battle', text)

    def populate_profiles(self):
        if hasattr(self,'welcome'):self.welcome.setVisible(not self.profiles)
        for control in self.engines:
            index = control.currentIndex()
            control.clear()
            control.addItems([p.name for p in self.profiles])
            control.setCurrentIndex(max(0, index))

    def load_engine(self, side):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose chess engine executable',
            self.db.get('engine_directory',''), 'Windows engine (*.exe);;All files (*)' if sys.platform == 'win32' else 'All files (*)')
        if not path:return
        dialog = ProfileDialog(self, selected_path=path)
        if dialog.exec() != QDialog.DialogCode.Accepted:return
        self.profiles.append(dialog.profile)
        self.db.put('profiles',[asdict(p) for p in self.profiles])
        self.db.put('engine_directory',str(Path(path).parent))
        self.populate_profiles()
        self.engines[side].setCurrentIndex(len(self.profiles)-1)
        if len(self.profiles)==1:self.engines[1-side].setCurrentIndex(0)
        self.welcome.hide()
        self.status.setText('Engine ready: '+dialog.profile.name+'. Both sides can use the same engine with different search budgets.')
        self.workspace.setCurrentIndex(0)
        self.save_settings()

    def unload_engine(self, side):
        if self.tournament.active:
            self.error('Pause the match before unloading an engine.');return
        self.cancel_analysis()
        self.analysis.engine.connection.close()
        self.tournament.search.engine.connection.close()
        self.engines[side].setCurrentIndex(-1)
        self.status.setText('Engine '+'AB'[side]+' unloaded. Its saved settings and game history are retained. Choose a saved engine or open another file.')
        self.refresh_analysis()
        self.save_settings()

    def add_profile(self):
        if not self.profiles or self.engines[0].currentIndex()<0:
            self.status.setText('Select a saved Engine A first, or click Open engine file above.');return
        source = self.profiles[self.engines[0].currentIndex()] if self.profiles else None
        dialog = ProfileDialog(self, source)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.profiles.append(dialog.profile)
            self.db.put('profiles', [asdict(p) for p in self.profiles])
            self.populate_profiles()
            self.engines[1].setCurrentIndex(len(self.profiles)-1)

    def edit_profile(self):
        if not self.profiles or self.engines[0].currentIndex()<0: return
        index = self.engines[0].currentIndex()
        dialog = ProfileDialog(self, self.profiles[index])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.profile.id = self.profiles[index].id
            self.profiles[index] = dialog.profile
            self.db.put('profiles', [asdict(p) for p in self.profiles])
            self.populate_profiles()

    def remove_profile(self):
        if not self.profiles or self.engines[0].currentIndex()<0: return
        if QMessageBox.question(self, 'Remove profile', 'Remove this profile? Historical searches are retained.') != QMessageBox.StandardButton.Yes: return
        self.profiles.pop(self.engines[0].currentIndex())
        self.db.put('profiles', [asdict(p) for p in self.profiles]); self.populate_profiles()

    def swap_budgets(self):
        a,b = [c.text() for c in self.budgets]
        self.budgets[0].setText(b); self.budgets[1].setText(a)

    def change_workspace(self, index):
        self.config_scroll.setVisible(index == 0)
        self.tabs.parentWidget().setVisible(index != 0)
        if index == 1: self.tabs.setCurrentIndex(3)
        if index == 2: self.tabs.setCurrentIndex(0)
        if index == 3: self.tabs.setCurrentIndex(2)
        if index == 4: self.tabs.setCurrentIndex(5)

    def open_archive(self):
        if self.tournament.active:
            self.error('Pause the match before opening an archived tournament.'); return
        sid = self.archive_selector.currentData()
        if not sid: return
        self.tournament.state = self.db.get('tournament:'+sid)
        self.tournament.restore_game()
        self.follow_live = True
        self.tournament.save()
        profiles = [Profile(**p) for p in self.tournament.state['profiles']]
        for side, profile in enumerate(profiles):
            index = next((i for i,p in enumerate(self.profiles) if p.fingerprint() == profile.fingerprint()), -1)
            if index < 0:
                self.profiles.append(profile); self.populate_profiles(); index = len(self.profiles)-1
            self.engines[side].setCurrentIndex(index)
        self.match_changed()

    def filter_games(self):
        self.games_table.proxy.setFilterFixedString(self.game_filter.text())

    def table_game(self, row, col):
        self.select_game(self.games_table.source_row(row))

    def inspect_candidate(self, side, record, rank):
        self.graph_select(side,record)
        self.panels[side].pv_rank.setValue(rank)

    def selected_profiles(self):
        if not self.profiles or any(c.currentIndex()<0 for c in self.engines):
            raise ValueError('Choose an engine for both A and B. Use Open engine file above or select a saved engine.')
        return [self.profiles[c.currentIndex()] for c in self.engines]

    def update_pair_description(self):
        self.pair_description.setText(f'{self.pairs.value()} opening pairs = {self.pairs.value()*2} games. Each selected opening gets two games with colors swapped. Extra pairs repeat the suite.')

    def search_mode_changed(self,mode):
        self.clock_button.setVisible(mode == 'clock')
        for field in self.budgets:
            field.setEnabled(mode != 'clock');field.setVisible(mode != 'clock')
            self.limit_form.labelForField(field).setVisible(mode != 'clock')
        self.ratio_button.setVisible(mode=='nodes')
        self.swap_budget_button.setVisible(mode!='clock')

    def update_clocks(self):
        clock=self.tournament.clock
        if not clock:self.clock_label.clear();return
        def label(color):
            milliseconds=clock.left(color)//1_000_000
            return f'{milliseconds//60000:02d}:{milliseconds//1000%60:02d}.{milliseconds%1000//100}'
        self.clock_label.setText(f'Live clocks · White {label(1)}   |   Black {label(-1)}')

    def limits(self):
        mode = self.mode.currentText()
        if mode == 'clock':
            return [Limit('clock',round(base.value()*60000),round(inc.value()*1000)) for base,inc in zip(self.clock_bases,self.clock_increments)]
        result = [Limit(mode, parse_budget(c.text()) if mode != 'movetime' else float(c.text())) for c in self.budgets]
        for limit in result:
            limit.validate()
        return result

    def bounds(self):
        from .history import Checkpoints
        start = parse_budget(self.checkpoint.text())
        maximum = int(self.maximum.text()) if self.maximum.text().strip() else None
        Checkpoints(start, maximum)
        return start, maximum

    def apply_ratio(self):
        try:
            if self.mode.currentText() != 'nodes':
                raise ValueError('Node ratios require fixed nodes mode')
            from decimal import Decimal
            value = Decimal(parse_budget(self.budgets[0].text())) * Decimal(self.ratio.currentText())
            if value <= 0 or value != int(value):
                raise ValueError('Ratio must produce a positive integer node budget')
            self.budgets[1].setText(str(int(value)))
        except Exception as exc:
            self.error(str(exc))

    def use_full_opening_suite(self):
        try:
            count=len(openings(self.book.text()))
            self.pairs.setValue(count)
            self.status.setText(f'{count} opening entries selected: {count*2} games with colors reversed.')
        except (ValueError,OSError) as exc:self.error(str(exc))

    def choose_book(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose opening suite', filter='Opening suites (*.pgn *.epd)')
        if path:
            try:
                fens = openings(path)
                self.book.setText(path)
                self.status.setText(f'Validated {len(fens)} opening positions. First: {fens[0]}')
                self.board.show_preview(Board(str(fens[0])), caption='Opening preview')
                recent = self.db.get('recent_books', [])
                self.db.put('recent_books', ([path]+[p for p in recent if p != path])[:10])
            except (ValueError, OSError) as exc:
                self.error(str(exc))

    def start_match(self):
        try:
            profiles, limits = self.selected_profiles(), self.limits()
            start, maximum = self.bounds()
            if self.tournament.state:
                old = self.tournament.state
                self.db.put('tournament:'+old['id'], old)
            description = '\n'.join(f"{p.name}: "+(f"{l.value/60000:g} min + {l.increment_ms/1000:g} sec" if l.mode=='clock' else f"{l.value:,} {l.mode}")+f", Threads={p.options.get('Threads','default')}, Hash={p.options.get('Hash','default')}" for p,l in zip(profiles,limits))
            description += f"\n{self.pairs.value()*2} games · {self.book.text() or 'start position'} · Playing PV{self.play_pv.value()} · checkpoints from {start:,}"
            self.summary.setText(description)
            if QMessageBox.question(self, 'Match configuration', description+'\nStart this match?') != QMessageBox.StandardButton.Yes: return
            self.cancel_analysis()
            self.tournament.create(profiles, limits, schedule(openings(self.book.text()),
                self.pairs.value(), self.seed.value(), self.randomized.isChecked()),
                self.play_pv.value(), start, maximum, self.seed.value())
            self.tournament.state['silence_timeout_ms']=self.silence_timeout.value()*1000
            self.tournament.save()
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
            self.games_table.hide();self.game_filter.hide()
            self.show_game()
            return
        self.games_table.show();self.game_filter.show()
        self.game_selector.blockSignals(True)
        current = self.game_selector.currentIndex()
        if self.game_selector.count() != len(state['games']):
            self.game_selector.clear()
            self.game_selector.addItems([str(i+1) for i in range(len(state['games']))])
        index = min(state['index'], len(state['games'])-1) if self.follow_live else max(0, current)
        self.game_selector.setCurrentIndex(index)
        self.game_selector.blockSignals(False)
        if self.follow_live:
            self.load_game(index)
        self.games_table.games.update_state(state,self.tournament.active,{state['index'],getattr(self,'_browser_index',state['index'])})
        self._browser_index=state['index']
        from .statistics import summarize
        statistics_key=(state['id'],tuple(g['result'] for g in state['games']))
        if getattr(self,'_statistics_key',None)!=statistics_key:
            self.stats.setPlainText(summarize(state));self._statistics_key=statistics_key
        self.update_clocks()
        self.status.setText(f"{'Running' if self.tournament.active else 'Paused / complete'} · game {index+1}/{len(state['games'])}")

    def live_info(self, info):
        game = self.tournament.game
        if not game or not self.tournament.active:
            return
        item = self.tournament.state['games'][self.tournament.state['index']]
        side = 0 if ((game.board.turn == 1) == item['a_white']) else 1
        panel = self.panels[side]
        position = game.board.fen()
        if self.live_positions[side] != position:
            self.live_panels[side].clear(); self.live_positions[side] = position
        self.live_labels[side].setText(f"Live engine {'AB'[side]} · ply {game.cursor} · {position}")
        if True:
            self.live_panels[side].set_multipv(self.tournament.state['multipv'])
            self.live_panels[side].update_line(info, game.board.turn)
        if self.follow_live:self.evalbar.set_score(info.get('score',0)*game.board.turn)
        self.status.setText(f"Playing · Engine {'AB'[side]} · {info.get('nodes', 0):,} reported nodes")

    def load_game(self, index):
        state = self.tournament.state
        item = state['games'][index]
        moves=item['moves']
        existing=self.view_game
        prefix=[move.uci() for move in existing.moves]
        reusable=(item.get('id') == existing.id and existing.initial_fen == item['fen']
                  and existing.cursor == len(prefix) and prefix == moves[:len(prefix)])
        if not reusable:
            self.view_game = Game(item['fen'])
            self.view_game.id = item.get('id',self.view_game.id)
            prefix=[]
        for uci in moves[len(prefix):]:
            self.view_game.play(self.view_game.board.parse_uci(uci))
        self.show_game()

    def select_game(self, index):
        if self.tournament.state and index >= 0:
            self.game_selector.blockSignals(True)
            self.game_selector.setCurrentIndex(index)
            self.game_selector.blockSignals(False)
            self.follow_live = False
            self.load_game(index)

    def navigate(self, cursor):
        self.follow_live = False
        self.view_game.navigate(max(0, min(len(self.view_game.moves), cursor)))
        self.show_game()

    def original_thinking(self):
        ply = self.view_game.cursor
        if not ply:return
        state = self.tournament.state
        item = state['games'][self.game_selector.currentIndex()] if state else {}
        link = item.get('move_searches',{}).get(str(ply))
        self.navigate(ply-1)
        if link:
            run = self.db.search_run(link['search_run_id'])
            from .model import position_identity
            if not run or run['position'] != position_identity(self.view_game) or run['game'] != self.view_game.id:
                self.status.setText('Recorded search attribution is missing or incompatible.');return
            profile = Profile(**run['profile'])
            self.syncing=True
            self.panels[0].load(self.db.records(self.view_game,profile),self.view_game.board.turn,[run])
            self.panels[1].load([],self.view_game.board.turn,[])
            self.syncing=False
            self.selection_changed(0)
            self.panels[0].title.setText('PLAYING ENGINE · exact move source')
            self.panels[1].title.setText('No second playing search for this move')
            self.status.setText('Exact played-move source: '+run['id'])
        else:
            for side,panel in enumerate(self.panels):
                runs = self.db.runs(self.view_game,self.selected_profiles()[side])
                candidates = [r for r in runs if r['provenance']=='live-playing' and r['game']==self.view_game.id]
                if len(candidates)==1:panel.run.setCurrentIndex(panel.run.findData(candidates[0]['id']))
            self.status.setText('Legacy move: source search not recorded. Compatible history is uncertain attribution.')
        self.workspace.setCurrentIndex(2)

    def return_live(self):
        self.follow_live = True
        self.match_changed()

    def show_game(self):
        game = self.view_game
        last = game.moves[game.cursor-1] if game.cursor else None
        self.board.set_position(game.board.copy(), last)
        self.position_label.setText(f"{'Live' if self.follow_live else 'Historical'} · ply {game.cursor} · "
                                    f"{'White' if game.board.turn == 1 else 'Black'} to move")
        self.moves.setHtml(' '.join(f'<a href="{i+1}" style="color:{"#72c9bd" if i+1 == game.cursor else "#aab6c3"}">{i//2+1 if i%2==0 else ""} {text}</a>' for i,text in enumerate(game.sans)))
        for panel in self.panels:
            panel.pin_control.setChecked(False)
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
        for side,panel in enumerate(self.panels):
            index=self.engines[side].currentIndex()
            profile=self.profiles[index] if index>=0 else None
            panel.title.setText('ENGINE '+'AB'[side])
            panel.load(self.db.records(self.view_game,profile) if profile else [], self.view_game.board.turn if self.perspective.currentIndex() == 0 else 1, self.db.runs(self.view_game,profile) if profile else [])
        self.syncing = False
        self.selection_changed(0)

    def update_history(self):
        self.candidate_views.refresh(self.panels)
        self.graph.series = [panel.records for panel in self.panels]
        self.graph.update()
        from .history import milestones
        events = [f"{'AB'[side]} · {node_label(nodes)}: {text}" for side,panel in enumerate(self.panels) for nodes,text in milestones(panel.records)]
        self.discovery.clear()
        for side,panel in enumerate(self.panels):
            for nodes,text in milestones(panel.records):
                item=QListWidgetItem(f"{'AB'[side]} · {node_label(nodes)}: {text}")
                item.setData(Qt.ItemDataRole.UserRole,(side,nodes));self.discovery.addItem(item)
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
                if record and source.record['requested']:
                    label += f"Selected target ratio {record['requested']/source.record['requested']:.3g}×; reported-node ratio {record['actual']/max(1,source.record['actual']):.3g}×. "
                if record:
                    target.checkpoint.setCurrentIndex(target.records.index(record))
            a, b = [p.record for p in self.panels]
            result = compare(a, b, self.panels[0].pv_rank.value(), self.panels[1].pv_rank.value())
            self.comparison.setText(label + result['status'] +
                (f" · overlap (move, A rank, B rank): {result.get('overlap')}\n"
                 f"Unique A: {result.get('only_a')} · Unique B: {result.get('only_b')} · "
                 f"Shared PV prefix: {result.get('shared_prefix')} plies · divergence: {result.get('divergence')}"
                 if 'overlap' in result else ''))
            self.highlight_comparison(a,b,result)
            line = a['lines'].get('1', {}) if a else {}
            self.evalbar.set_score(line.get('score', 0)*self.view_game.board.turn if line else None)
        except ValueError as exc:
            self.comparison.setText(str(exc))
        finally:
            self.syncing = False
        self.update_history()

    def milestone_clicked(self,item):
        side,nodes=item.data(Qt.ItemDataRole.UserRole)
        record=next((r for r in self.panels[side].records if r['requested']==nodes),None)
        if record:self.graph_select(side,record)

    def highlight_comparison(self, a, b, result):
        from PySide6.QtWidgets import QTextEdit
        from PySide6.QtGui import QTextCursor
        common = {m for m,_,_ in result.get('overlap', [])}
        for side, panel in enumerate(self.panels):
            for rank, (_, header, moves) in panel.panel.rows.items():
                line = panel.panel.lines.get(rank, {})
                pv = line.get('pv', [])
                header.setText(('Shared candidate' if pv and pv[0] in common else 'Unique / unavailable candidate')+f' · rank {rank}')
                header.show()
                selections = []
                divergence = result.get('divergence')
                if rank == panel.pv_rank.value() and divergence:
                    cursor = QTextCursor(moves.document())
                    while not cursor.atEnd():
                        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                        if cursor.charFormat().anchorHref() == f'move:{divergence}':
                            extra = QTextEdit.ExtraSelection(); extra.cursor = QTextCursor(cursor)
                            extra.format.setBackground(QColor('#68532f')); selections.append(extra)
                        cursor.clearSelection()
                moves.setExtraSelections(selections)

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
            if any(limit.mode == 'clock' for limit in limits):raise ValueError('Game clocks are for match play. Choose nodes, depth or fixed time for supplementary analysis.')
            start, maximum = self.bounds()
            game = Game.from_dict(self.view_game.to_dict())
            state = self.tournament.state
            index = self.game_selector.currentIndex()
            provenance = ('supplementary-during-match' if state and index >= 0 and
                          state['games'][index]['result'] == '*' else 'post-game')
            kind = 'independent' if self.analysis_kind.currentIndex() else 'continuous'
            for profile, limit in zip(profiles, limits):
                budgets = [limit]
                if kind == 'independent':
                    if limit.mode != 'nodes': raise ValueError('Independent checkpoints require node mode')
                    budgets = []; target = start
                    while target <= limit.value and (maximum is None or target <= maximum):
                        budgets.append(Limit('nodes',target)); target *= 2
                    if not budgets: raise ValueError('Budget is below the first checkpoint')
                self.queue.extend((game, profile, budget, self.supp_pv.value(), start, maximum, provenance,kind) for budget in budgets)

            self.run_next()
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def run_next(self):
        if self.queue:
            game, profile, limit, pv, start, maximum, provenance, kind = self.queue.pop(0)
            try:
                self.status.setText('Supplementary analysis: ' + profile.name)
                self.analysis.start(game, profile, limit, pv, provenance, start, maximum, kind=kind,silence_timeout_ms=self.silence_timeout.value()*1000)
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
                        if item.get('termination'):game.headers['Termination']=item['termination']
                        if all(limit['mode']=='clock' for limit in state['limits']):
                            controls=[f"{limit['value']/1000:g}+{limit.get('increment_ms',0)/1000:g}" for limit in state['limits']]
                            game.headers['TimeControl']=controls[0] if controls[0]==controls[1] else '?'
                            game.headers['WhiteTimeControl']=controls[white]
                            game.headers['BlackTimeControl']=controls[1-white]
                        game._main_result = item['result']
                        texts.append(game.pgn())
                Path(path).write_text('\n\n'.join(texts), encoding='utf-8')
            else:
                raise ValueError('Choose .json, .csv or .pgn')
            self.status.setText('Exported ' + path)
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def save_settings(self):
        self.db.put('workspace', dict(clock_bases=[c.value() for c in self.clock_bases],clock_increments=[c.value() for c in self.clock_increments],silence_timeout=self.silence_timeout.value(), geometry=bytes(self.saveGeometry().toHex()).decode(), workspace=self.workspace.currentIndex(), splitter=self.splitter.sizes(), mode=self.mode.currentText(),
            budgets=[x.text() for x in self.budgets], engines=[x.currentIndex() for x in self.engines],
            book=self.book.text(), pairs=self.pairs.value(), play_pv=self.play_pv.value(),
            checkpoint=self.checkpoint.text(), maximum=self.maximum.text(), seed=self.seed.value(),
            randomized=self.randomized.isChecked(), ratio=self.ratio.currentText(), dual=self.dual.isChecked()))

    def restore_settings(self):
        state = self.db.get('workspace')
        if not state:
            return
        if state.get('geometry'): self.restoreGeometry(bytes.fromhex(state['geometry']))
        self.workspace.setCurrentIndex(state.get('workspace',0))
        self.silence_timeout.setValue(state.get('silence_timeout',120))
        self.splitter.setSizes(state['splitter'])
        self.mode.setCurrentText(state['mode'])
        for control,value in zip(self.clock_bases,state.get('clock_bases',[10/60,10/60])):control.setValue(value)
        for control,value in zip(self.clock_increments,state.get('clock_increments',[0.1,0.1])):control.setValue(value)
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
    from PySide6.QtCore import QLockFile
    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(directory / 'battle.lock'))
    if not lock.tryLock(0):
        print('Nocturne Battle is already using this library.', file=sys.stderr)
        return 1
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
