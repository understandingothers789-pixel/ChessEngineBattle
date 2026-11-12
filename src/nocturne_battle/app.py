"""Standalone native match and exact-position search inspection workspace."""
from dataclasses import asdict
import csv
import json
import math
import sqlite3
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QStandardPaths, Signal, QTimer, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QKeySequence, QShortcut, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QSplitter, QScrollArea, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem, QPlainTextEdit, QTextBrowser, QListWidget,QListWidgetItem)
from nocturne.core.game import Game
from nocturne.core.board import Board
from nocturne.engine.uci_types import score_label
from nocturne.gui.board import BoardWidget
from nocturne.gui.candidates import CandidatePanel
from nocturne.gui.moves import MoveText
from .theme import stylesheet
from .match_panel import MatchCandidates
from .match_files import write_match, read_match
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
        self.setWindowTitle('Chess Engine Battle 0.4.0 · Engine Match & Analysis Studio')
        self.resize(1800, 1000)
        self.profiles = [Profile(**p) for p in db.get('profiles', [])]
        self.tournament = Tournament(db, self)
        self.tournament.changed.connect(self.match_changed)
        self.tournament.failed.connect(self.error)
        self.tournament.clock_changed.connect(self.update_clocks)
        self.tournament.search.updated.connect(self.live_info)
        self.tournament.search.started.connect(self.live_started)
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
        title = QLabel('CHESS ENGINE BATTLE  /  MATCH & ANALYSIS')
        title.setStyleSheet('font-size: 21px; font-weight: 600; color: #263e50; padding: 8px;')
        outer.addWidget(title)
        quick = QHBoxLayout()
        self.load_a_button = button('Load engine A…', lambda:self.load_engine(0), quick)
        self.load_b_button = button('Load engine B…', lambda:self.load_engine(1), quick)
        for control in (self.load_a_button,self.load_b_button):
            control.setToolTip('Choose a local UCI engine executable, such as Stockfish. Test it and save its settings to use it in matches.')
        button('Match setup…', self.open_setup, quick)
        self.save_match_button = button('Save match…', self.save_match_file, quick)
        self.save_match_button.setObjectName('saveMatch')
        self.save_match_button.setToolTip('Save a portable copy of this tournament, including every recorded move, engine variation, depth and checkpoint. Play pauses while saving.')
        button('Saved matches…', self.open_library, quick)
        self.pause_button = button('Pause', self.toggle_pause, quick)
        self.pause_button.setToolTip('Pause engine searches and freeze both clocks. Click Resume to continue the current match.')
        self.adjudicate_button = button('Adjudicate game…', self.adjudicate_game, quick)
        outer.addLayout(quick)
        self.workspace = QComboBox()
        self.workspace.addItems(['Match Setup', 'Live Match', 'Analysis Comparison', 'Results & History', 'Node Scaling Experiment'])
        outer.addWidget(self.workspace)

        self.splitter = QSplitter()
        outer.addWidget(self.splitter)
        board_area = QWidget()
        board_layout = QVBoxLayout(board_area)
        self.match_banner = QLabel('Ready · load two engines, then open Match setup')
        self.match_banner.setObjectName('matchBanner'); self.match_banner.setWordWrap(True)
        board_layout.addWidget(self.match_banner)
        self.position_label = QLabel('Game position')
        board_layout.addWidget(self.position_label)
        self.clock_label=QLabel('')
        self.clock_label.setToolTip('Live game clocks. Preparation is excluded; each accepted move earns its increment. Pausing freezes the remaining time.')
        self.clock_label.setStyleSheet('font-size: 19px; padding: 6px;')
        board_layout.addWidget(self.clock_label)
        board_row = QHBoxLayout()
        self.board = BoardWidget()
        self.board.interactive = False
        self.board.theme = 'Forest'
        self.board.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        self.game_selector.hide()
        self.game_filter = QLineEdit()
        self.game_filter.setPlaceholderText('Filter games by engine, pair, result or status')
        self.game_filter.textChanged.connect(self.filter_games)

        self.games_table = GameBrowser()
        self.games_table.setMaximumHeight(130)
        self.games_table.clicked.connect(lambda index:self.table_game(index.row(),index.column()))

        self.moves = QTextBrowser()
        self.moves.setOpenLinks(False)
        self.moves.anchorClicked.connect(lambda url: self.inspect_move(int(url.toString())))
        self.moves.setReadOnly(True)
        self.moves.setMinimumHeight(85)
        self.moves.setMaximumHeight(120)
        self.moves.setToolTip('Click any played move to see its saved engine variations on the right. Arrow keys review earlier or later moves. Opening-book moves have no engine search.')
        board_layout.addWidget(QLabel('MOVES · click a move to review its saved analysis'))
        board_layout.addWidget(self.moves)
        games_group = QGroupBox('Games in this match'); games_group.setCheckable(True); games_group.setChecked(False)
        games_layout = QVBoxLayout(games_group)
        self.games_body = QWidget(); games_body = QVBoxLayout(self.games_body)
        games_body.addWidget(self.game_filter); games_body.addWidget(self.games_table)
        games_layout.addWidget(self.games_body); self.games_body.hide()
        games_group.toggled.connect(self.games_body.setVisible)
        games_group.setMaximumHeight(34)
        games_group.toggled.connect(lambda expanded:games_group.setMaximumHeight(230 if expanded else 34))
        board_layout.addWidget(games_group)
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
        self.analysis_controls = [self.perspective,self.dual,self.link,self.ratio,compact]
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
        metric.currentIndexChanged.connect(lambda index:(setattr(self.graph,'metric_name','depth' if index else 'evaluation'),self.graph.update()))
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
        self.analysis_heading = QLabel('Engine analysis')
        self.analysis_heading.setWordWrap(True)
        self.analysis_heading.setStyleSheet('font-size: 19px; font-weight: bold; padding: 6px;')
        live_layout.addWidget(self.analysis_heading)
        hint = QLabel('Analysis is saved automatically for every engine move. Click a move on the left to review it, or hover a variation for a board preview.')
        hint.setWordWrap(True); live_layout.addWidget(hint)
        hint.setToolTip(f'Games and engine analysis are saved automatically in {self.db.path}. Close the app before backing up this file. Select a played move to view its saved variations here.')
        analysis_actions = QHBoxLayout()
        follow = button('Follow live game', self.return_live, analysis_actions); follow.setObjectName('followLive')
        self.full_variations = QCheckBox('Full variations')
        self.full_variations.setToolTip('By default show the first 6 half-moves (3 full moves). Enable to display the entire variation. Complete lines are always saved.')
        self.full_variations.toggled.connect(lambda full:[p.set_full(full) for p in self.live_panels])
        analysis_actions.addWidget(self.full_variations); live_layout.addLayout(analysis_actions)
        self.saved_selectors = []
        self.saved_records = [[], []]
        self.live_panels = []
        self.live_labels = []
        self.live_positions = [None,None]
        self.live_games = [None, None]
        self.live_search_ids = [None, None]
        for side in range(2):
            panel = MatchCandidates(MoveText(auto_fit=True))
            panel.set_maia(enabled=False)
            panel.show_line_depth = True
            panel.show_seldepth = True
            panel.preview.connect(lambda rank, ply, s=side: self.live_preview(s, rank, ply))
            panel.preview_end.connect(self.clear_live_preview)
            label = QLabel('Live engine '+ 'AB'[side]); label.setWordWrap(True)
            self.live_labels.append(label); live_layout.addWidget(label)
            selector = QComboBox(); selector.hide()
            selector.setToolTip('Review the final variations or an earlier saved depth/checkpoint for this exact playing search.')
            selector.currentIndexChanged.connect(lambda index, s=side:self.choose_saved(s,index))
            self.saved_selectors.append(selector); live_layout.addWidget(selector)
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)
            scroll.setMinimumHeight(80); scroll.setMaximumHeight(215)
            panel.changed.connect(lambda p=panel,s=scroll:s.setFixedHeight(min(250,max(90,p.multipv*38+14))))
            live_layout.addWidget(scroll)
            self.live_panels.append(panel)
        self.preview_popup = QDialog(self, Qt.WindowType.ToolTip)
        self.preview_popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        popup_layout = QVBoxLayout(self.preview_popup); popup_layout.setContentsMargins(4,4,4,4)
        self.live_preview_board = BoardWidget(); self.live_preview_board.interactive = False
        self.live_preview_board.setFixedSize(270, 270); self.live_preview_board.hide()
        popup_layout.addWidget(self.live_preview_board)
        live_layout.addStretch(1)
        self.live_area = live
        work_layout.insertWidget(0, live, 1)
        self.tabs.addTab(QLabel('Live and saved engine analysis is shown above.'), 'Live Match')
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
        book_note = QLabel('Opening books are a separate download. Extract them to a folder you keep, then Browse to select a PGN or EPD file. Your recent paths are saved.')
        book_note.setWordWrap(True); form.addRow(book_note)
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
        self.play_pv.setValue(3)
        self.play_pv.setToolTip('Number of candidate variations each playing engine searches and saves for every move. More variations can reduce playing strength at the same time or node budget. Requires engine MultiPV support.')
        form.addRow('Playing MultiPV', self.play_pv)
        self.auto_draw = QCheckBox('Automatic draw by evaluation agreement')
        self.auto_draw.setChecked(True)
        self.auto_draw.setToolTip('After move 50, draw when both engines stay within ±0.20 pawns for 10 consecutive plies (5 full moves). Uses exact rank-1 scores from consecutive completed playing searches. Missing or non-exact scores reset the streak.')
        form.addRow(self.auto_draw)
        rule_note = QLabel('After move 50 · both within ±0.20 pawns · 10 consecutive plies')
        rule_note.setWordWrap(True); form.addRow(rule_note)
        self.checkpoint = QLineEdit('1000000')
        form.addRow('First checkpoint', self.checkpoint)
        self.summary = QLabel(); self.summary.setWordWrap(True)
        config.addWidget(self.summary)
        button('Review & Start Match', self.start_match, config)
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
        self.setup_dialog = QDialog(self); self.setup_dialog.setWindowTitle('Match setup')
        self.setup_dialog.resize(680, 800)
        setup_layout = QVBoxLayout(self.setup_dialog); setup_layout.addWidget(scroll)
        button('Done', self.setup_dialog.hide, setup_layout)
        self.splitter.setSizes([1000, 500])
        self.config_scroll = scroll
        self.workspace.currentIndexChanged.connect(self.change_workspace)
        self.populate_profiles()
        self.restore_settings()
        self.workspace.setCurrentIndex(1)
        self.change_workspace(1)
        self.board.wheel_navigated.connect(lambda delta: self.navigate(self.view_game.cursor+delta))
        for key, callback in [('Left', lambda: self.navigate(self.view_game.cursor-1)),
                              ('Right', lambda: self.navigate(self.view_game.cursor+1))]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        self.match_changed()
        if self.tournament.state:self.restore_live_analysis()
        from .help import install_tooltips
        install_tooltips(self)

    def error(self, text):
        self.status.setText(text)
        QMessageBox.warning(self, 'Chess Engine Battle', text)

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

    def open_setup(self):
        self.setup_dialog.show(); self.setup_dialog.raise_(); self.setup_dialog.activateWindow()

    def toggle_pause(self):
        if self.tournament.active:self.tournament.pause()
        else:self.resume()

    def change_workspace(self, index):
        if index == 0:
            self.open_setup()
            self.workspace.setCurrentIndex(1)
            return
        self.live_area.setVisible(index == 1)
        self.tabs.setVisible(index != 1)
        self.comparison.setVisible(index != 1)
        for control in self.analysis_controls:control.setVisible(index != 1)
        if index == 2:self.tabs.setCurrentIndex(0)
        if index == 3:self.tabs.setCurrentIndex(2)
        if index == 4:self.tabs.setCurrentIndex(5)

    def open_archive(self):
        if self.tournament.active:self.tournament.pause()
        self.cancel_analysis()
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
        self.db.put('profiles',[asdict(p) for p in self.profiles])
        self._live_game_id = None
        for panel in self.live_panels:panel.clear()
        self.workspace.setCurrentIndex(1)
        self.match_changed()
        self.restore_live_analysis()
        self.games_body.parentWidget().setChecked(True)

    def refresh_archives(self):
        self.archive_selector.clear()
        self.archive_selector.addItem('Select a saved tournament…',None)
        from datetime import datetime
        for state in self.db.archives():
            count = sum(g['result'] != '*' for g in state['games'])
            date = datetime.fromtimestamp(state['created_at']).strftime('%b %d, %Y %H:%M') if state.get('created_at') else 'Earlier match'
            name = state.get('name') or ' vs '.join(p['name'] for p in state['profiles'])
            self.archive_selector.addItem(f"{name} · {date} · {count}/{len(state['games'])} games",state['id'])

    def save_match_file(self):
        if not self.tournament.state:return
        was_active = self.tournament.active
        self.tournament.pause()
        try:
            from datetime import datetime
            suggestion = 'Engine match '+datetime.now().strftime('%Y-%m-%d %H%M')+'.cebattle'
            path,_ = QFileDialog.getSaveFileName(self,'Save tournament with all analysis',suggestion,'Chess Engine Battle match (*.cebattle)')
            if not path:return
            if not Path(path).suffix:path += '.cebattle'
            snapshot = json.loads(json.dumps(self.tournament.state))
            snapshot['name'] = Path(path).stem
            write_match(self.db,snapshot,path)
            self.tournament.state['name'] = snapshot['name']; self.tournament.save()
            self.refresh_archives()
            self.status.setText(f'Saved match and recorded engine analysis to {path}')
        except (ValueError,OSError) as exc:self.error(str(exc))
        finally:
            if was_active:self.tournament.resume()

    def open_library(self):
        self.refresh_archives()
        dialog = QDialog(self); dialog.setWindowTitle('Saved matches'); dialog.resize(800,500)
        layout = QVBoxLayout(dialog)
        note = QLabel('Every tournament is saved automatically in your library. Save match creates a portable copy with its recorded engine analysis. Select a match to review its games, then click any move to see its variations.')
        note.setWordWrap(True); layout.addWidget(note)
        matches = QListWidget(); layout.addWidget(matches,1)
        def refresh():
            self.refresh_archives(); matches.clear()
            for i in range(1,self.archive_selector.count()):
                row = QListWidgetItem(self.archive_selector.itemText(i))
                row.setToolTip(row.text())
                row.setData(Qt.ItemDataRole.UserRole,self.archive_selector.itemData(i)); matches.addItem(row)
            if matches.count():matches.setCurrentRow(0)
        def open_selected():
            row = matches.currentItem()
            if not row:return
            self.archive_selector.setCurrentIndex(self.archive_selector.findData(row.data(Qt.ItemDataRole.UserRole)))
            self.open_archive(); dialog.accept()
        def import_file():
            path,_ = QFileDialog.getOpenFileName(dialog,'Open saved match file',filter='Chess Engine Battle match (*.cebattle);;All files (*)')
            if not path:return
            try:
                sid = read_match(self.db,path)
                refresh()
                for i in range(matches.count()):
                    if matches.item(i).data(Qt.ItemDataRole.UserRole) == sid:matches.setCurrentRow(i);break
                open_selected()
            except (ValueError,OSError,KeyError,TypeError,AttributeError,sqlite3.Error) as exc:self.error(f'Could not open match file: {exc}')
        controls = QHBoxLayout(); layout.addLayout(controls)
        button('Open selected match',open_selected,controls)
        button('Open match file…',import_file,controls)
        button('Close',dialog.reject,controls)
        matches.itemDoubleClicked.connect(lambda _:open_selected())
        refresh(); dialog.exec()

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
            self.tournament.state['draw_rule']['enabled']=self.auto_draw.isChecked()
            self.tournament.save()
            self.follow_live = True
            self.save_settings()
            self.setup_dialog.hide()
            self.workspace.setCurrentIndex(1)
            self.tournament.resume()
        except (ValueError, OSError) as exc:
            self.error(str(exc))

    def resume(self):
        self.cancel_analysis()
        self.workspace.setCurrentIndex(1)
        self.tournament.resume()

    def adjudicate_game(self):
        if not self.tournament.game or self.tournament.game.outcome:
            self.error('There is no unfinished current game to adjudicate.'); return
        was_active = self.tournament.active
        self.tournament.pause()
        dialog = QDialog(self); dialog.setWindowTitle('Adjudicate current game')
        layout = QVBoxLayout(dialog); form = QFormLayout(); layout.addLayout(form)
        choice = QComboBox(); choice.addItems(['Use both engines’ evaluations', 'Draw', 'White wins', 'Black wins'])
        form.addRow('Result', choice)
        draw = QDoubleSpinBox(); draw.setRange(0, 10); draw.setValue(0.5); draw.setSuffix(' pawns')
        win = QDoubleSpinBox(); win.setRange(0.01, 100); win.setValue(2.0); win.setSuffix(' pawns')
        form.addRow('Draw: both within ±', draw); form.addRow('Win: both favor same side by at least', win)
        note = QLabel('The match is paused while you choose. Uses each engine’s latest completed playing search from the last two plies, normalized to White’s perspective. If scores are missing or disagree, the game continues. Explicit results override the evaluations. Applies to the current game; the match then continues.')
        note.setWordWrap(True); layout.addWidget(note)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Ok).setText('Adjudicate game')
        controls.accepted.connect(dialog.accept); controls.rejected.connect(dialog.reject); layout.addWidget(controls)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:return
            if draw.value() >= win.value() and choice.currentIndex() == 0:
                raise ValueError('The win threshold must be greater than the draw threshold.')
            self.tournament.adjudicate([None, '1/2-1/2', '1-0', '0-1'][choice.currentIndex()],
                draw_cp=round(draw.value()*100), win_cp=round(win.value()*100))
        except ValueError as exc:self.error(str(exc))
        finally:
            if was_active:self.tournament.resume()

    def match_changed(self):
        state = self.tournament.state
        self.pause_button.setText('Pause' if self.tournament.active else 'Resume')
        self.save_match_button.setEnabled(bool(state))
        if state:
            complete = sum(g['result'] != '*' for g in state['games'])
            mode = 'RUNNING' if self.tournament.active else ('COMPLETED' if complete == len(state['games']) else 'PAUSED')
            self.match_banner.setText(f"{mode} · {state.get('name','Engine match')} · {complete}/{len(state['games'])} games completed")
        self.pause_button.setEnabled(bool(state and state['index'] < len(state['games'])))
        if state and state.get('review_only'):
            self.pause_button.setText('Review only'); self.pause_button.setEnabled(False)
            self.pause_button.setToolTip('This portable copy is open for review. To play a new match, select your local engines in Match setup.')
        else:
            self.pause_button.setToolTip('Pause engine searches and freeze both clocks. Resume continues the current local match.')
        self.clock_label.setVisible(bool(self.tournament.clock))
        self.adjudicate_button.setEnabled(bool(self.tournament.game and not self.tournament.game.outcome))
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
            if not self.tournament.active and not any(p.lines for p in self.live_panels):self.restore_live_analysis()
        self.games_table.games.update_state(state,self.tournament.active,{state['index'],getattr(self,'_browser_index',state['index'])})
        self._browser_index=state['index']
        from .statistics import summarize
        statistics_key=(state['id'],tuple(g['result'] for g in state['games']))
        if getattr(self,'_statistics_key',None)!=statistics_key:
            self.stats.setPlainText(summarize(state));self._statistics_key=statistics_key
        self.update_clocks()
        self.status.setText(f"{'Running' if self.tournament.active else 'Paused / complete'} · game {index+1}/{len(state['games'])}")

    def clear_live_preview(self):
        self.live_preview_board.clear_preview(); self.preview_popup.hide()

    def choose_saved(self, side, index):
        if not 0 <= index < len(self.saved_records[side]):return
        record = self.saved_records[side][index]
        panel = self.live_panels[side]; panel.clear()
        lines = record.get('lines', {})
        panel.set_multipv(max([int(k) for k in lines] or [1]))
        for line in lines.values():panel.update_line(line, self.live_games[side].board.turn)

    def load_saved_analysis(self, item, ply):
        runs = {}
        for key, link in sorted(item.get('move_searches', {}).items(), key=lambda x:int(x[0]), reverse=True):
            if int(key) > ply:continue
            run = self.db.search_run(link['search_run_id'])
            if not run:continue
            side = 0 if (run['fen'].split()[1] == 'w') == item['a_white'] else 1
            if side not in runs:runs[side] = (int(key),run)
            if len(runs) == 2:break
        self.clear_live_preview()
        for side in range(2):
            selector = self.saved_selectors[side]
            selector.blockSignals(True); selector.clear()
            self.live_panels[side].clear(); self.live_games[side] = None
            self.saved_records[side] = []
            if side in runs:
                move_ply, run = runs[side]
                game = Game(run['initial_fen'])
                for uci in run['moves']:game.play(game.board.parse_uci(uci))
                game.id = run['game']; self.live_games[side] = game
                final = run.get('final_result', {})
                rows = [('Final variations', final)] if final.get('lines') else []
                rows += [(f"Depth {r['depth']} · saved variations", r) for r in final.get('depth_history', [])]
                rows += [(f"Checkpoint {r['actual']:,} nodes", r) for r in self.db.records(game,Profile(**run['profile'])) if r['id'] == run['id']]
                self.saved_records[side] = [r for _,r in rows]
                for label,_ in rows:selector.addItem(label)
                color = 'White' if run['fen'].split()[1] == 'w' else 'Black'
                self.live_labels[side].setText(f"Engine {'AB'[side]} · {run['profile']['name']} · {color} · saved search for ply {move_ply}")
                if not rows:self.live_labels[side].setText(self.live_labels[side].text()+' · no variations reported')
            else:
                self.live_labels[side].setText(f"Engine {'AB'[side]} · no recorded search yet (opening-book moves have no engine analysis)")
            selector.setVisible(bool(self.saved_records[side]))
            selector.setCurrentIndex(0); selector.blockSignals(False)
            self.choose_saved(side,0)

    def review_move(self, ply):
        state = self.tournament.state
        if not state:return
        self.follow_live = False
        self.workspace.setCurrentIndex(1)
        index = self.game_selector.currentIndex()
        if index < 0:return
        self.analysis_heading.setText(f'Saved analysis · through ply {ply}')
        self.load_saved_analysis(state['games'][index],ply)

    def restore_live_analysis(self):
        state = self.tournament.state
        if not state:return
        item = state['games'][min(state['index'],len(state['games'])-1)]
        self.load_saved_analysis(item,len(item['moves']))
        self.analysis_heading.setText('Live analysis · latest searches')
        if self.tournament.game:
            self._live_game_id = self.tournament.game.id
        self.live_search_ids = [None, None]
        if self.tournament.search.context:self.live_started(self.tournament.search.context, force=True)

    def live_preview(self, side, rank, ply):
        game = self.live_games[side]
        info = self.live_panels[side].lines.get(rank)
        if not game or not info:return
        board = game.board.copy(); last = None
        try:
            for uci in info['pv'][:ply]:
                last = board.parse_uci(uci); board.push(last)
        except ValueError:return
        self.live_preview_board.show()
        self.live_preview_board.show_preview(board, last, f'Engine {"AB"[side]} · PV{rank} · ply {ply}')
        point = QCursor.pos()+QPoint(20,20)
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.preview_popup.move(min(point.x(),area.right()-280),min(point.y(),area.bottom()-280))
        self.preview_popup.show()

    def live_started(self, context, force=False):
        # Clear even when a restarted search uses the same FEN as a previous run.
        game = self.tournament.game
        if not game or not self.follow_live:return
        item = self.tournament.state['games'][self.tournament.state['index']]
        if getattr(self, '_live_game_id', None) != game.id:
            for panel in self.live_panels:panel.clear()
            for side in range(2):self.live_labels[side].setText(f'Engine {"AB"[side]} · waiting for its first search')
            self.live_games = [None, None]; self.live_search_ids = [None, None]
            self._live_game_id = game.id
        side = 0 if (game.board.turn == 1) == item['a_white'] else 1
        if self.live_search_ids[side] == context['id'] and not force:return
        self.analysis_heading.setText('Live analysis · latest searches')
        for selector in self.saved_selectors:selector.hide()
        self.live_panels[side].clear()
        self.live_games[side] = Game(game.board.fen())
        self.live_search_ids[side] = context['id']
        self.live_positions[side] = game.board.fen()
        name = self.tournament.state['profiles'][side]['name']
        self.live_labels[side].setText(f'Engine {"AB"[side]} · {name} · {"White" if game.board.turn == 1 else "Black"} · searching before ply {game.cursor+1}')

    def live_info(self, info):
        game = self.tournament.game
        if not game or not self.tournament.active or not self.follow_live:
            return
        item = self.tournament.state['games'][self.tournament.state['index']]
        side = 0 if ((game.board.turn == 1) == item['a_white']) else 1
        position = game.board.fen()
        context = self.tournament.search.context
        if context and self.live_search_ids[side] != context['id']:self.live_started(context)
        name = self.tournament.state['profiles'][side]['name']
        self.live_labels[side].setText(f"Engine {'AB'[side]} · {name} · {'White' if game.board.turn == 1 else 'Black'} · latest search before ply {game.cursor+1} · depth {info.get('depth',0)} · {info.get('nodes',0):,} nodes")
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
            self.review_move(self.view_game.cursor)

    def navigate(self, cursor):
        self.follow_live = False
        self.view_game.navigate(max(0, min(len(self.view_game.moves), cursor)))
        self.show_game()
        self.review_move(self.view_game.cursor)

    def inspect_move(self, ply):
        self.navigate(ply)

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
            if self.panels[0].final_record:
                self.panels[0].checkpoint.setCurrentIndex(len(self.panels[0].records))
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
        self.workspace.setCurrentIndex(1)
        for selector in self.saved_selectors:selector.hide()
        self._live_game_id = None
        self.match_changed()
        self.restore_live_analysis()

    def show_game(self):
        game = self.view_game
        last = game.moves[game.cursor-1] if game.cursor else None
        self.board.set_position(game.board.copy(), last)
        self.position_label.setText(f"{'Live' if self.follow_live else 'Historical'} · ply {game.cursor} · "
                                    f"{'White' if game.board.turn == 1 else 'Black'} to move")
        initial = Game(game.initial_fen).board.native
        offset = 0 if initial.turn else 1
        cells = []
        for i,text in enumerate(game.sans):
            number = initial.fullmove_number + (i+offset)//2
            prefix = f'{number}.' if (i+offset)%2 == 0 else (f'{number}…' if i == 0 else '')
            color = '#137a70' if i+1 == game.cursor else '#304357'
            anchor = ' id="selected"' if i+1 == game.cursor else ''
            cells.append(f'<a{anchor} href="{i+1}" style="color:{color}; text-decoration:none;">{prefix} {text}</a>')
        self.moves.setHtml('<div style="font-size:15px; line-height:180%">'+' &nbsp; '.join(cells)+'</div>')
        self.moves.scrollToAnchor('selected')
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
                                            Result=item['result'], Event='Chess Engine Battle', Seed=str(state['seed']),
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
            ui_layout=2, full_variations=self.full_variations.isChecked(), book=self.book.text(), pairs=self.pairs.value(), play_pv=self.play_pv.value(), auto_draw=self.auto_draw.isChecked(),
            checkpoint=self.checkpoint.text(), maximum=self.maximum.text(), seed=self.seed.value(),
            randomized=self.randomized.isChecked(), ratio=self.ratio.currentText(), dual=self.dual.isChecked()))

    def restore_settings(self):
        state = self.db.get('workspace')
        if not state:
            return
        if state.get('geometry'): self.restoreGeometry(bytes.fromhex(state['geometry']))
        self.workspace.setCurrentIndex(state.get('workspace',0))
        self.silence_timeout.setValue(state.get('silence_timeout',120))
        self.splitter.setSizes(state['splitter'] if state.get('ui_layout') == 2 else [1000,500])
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
        self.full_variations.setChecked(state.get('full_variations',False))
        self.auto_draw.setChecked(state.get('auto_draw',True))
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
        self.setup_dialog.close()
        self.preview_popup.close()
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
    # Keep the established library location through the product rename.
    directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    app.setApplicationName('ChessEngineBattle')
    app.setApplicationDisplayName('Chess Engine Battle')
    app.setOrganizationName('Chess Engine Battle')
    app.setStyleSheet(stylesheet())
    from PySide6.QtCore import QLockFile
    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(directory / 'battle.lock'))
    if not lock.tryLock(0):
        print('Chess Engine Battle is already using this library.', file=sys.stderr)
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
