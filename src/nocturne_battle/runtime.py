"""Qt asynchronous orchestration on Nocturne's existing UCI controller."""
from dataclasses import asdict
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, Signal
from nocturne.core.game import Game
from nocturne.engine.uci_types import AnalysisLimits
from nocturne.gui.engine import EngineController

from .history import Checkpoints
from .model import Profile, Limit, executable_hash


class Search(QObject):
    updated = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.engine = EngineController(self)
        self.engine.set_history_capture(True)
        self.engine.connection.observation.connect(self.observe)
        self.engine.message.connect(self.message)
        self.engine.connection.configured.connect(self.configured)
        self.context = None
        self.generation = None

    def start(self, game, profile, limit, multipv=1, provenance='live-playing', start=1_000_000,
              maximum=None, tournament=None):
        self.cancel()
        limit.validate()
        if not 1 <= multipv <= 5:
            raise ValueError('MultiPV must be 1–5')
        identity = executable_hash(profile.path)
        if profile.network_files() != profile.networks:
            raise ValueError('External network file changed; revalidate its profile')
        if identity != profile.identity:
            raise ValueError('Engine executable changed; revalidate its profile')
        self.collector = Checkpoints(start, maximum)
        self.required = min(multipv, len(list(game.board.legal_moves())))
        self.context = self.db.begin(game, profile, limit, multipv, provenance, tournament)
        limits = AnalysisLimits(depth=int(limit.value) if limit.mode == 'depth' else 128,
                                seconds=float(limit.value) if limit.mode == 'movetime' else 1,
                                nodes=int(limit.value) if limit.mode == 'nodes' else None)
        try:
            self.generation = self.engine.start(game, limits, external=profile.path, options=profile.options,
                arguments=profile.arguments, multipv=multipv, nodes_only=limit.mode == 'nodes',
                time_nodes_only=limit.mode == 'movetime', time_enabled=limit.mode == 'movetime')
        except Exception:
            self.db.finish(self.context['id'], 'failed')
            self.context = None
            raise

    def configured(self):
        connection = self.engine.connection
        if self.context and connection.phase == "idle":
            requested = self.context["multipv"]
            if requested > 1 and int(connection.confirmed.get("MultiPV", 1)) != requested:
                self.cancel()
                self.failed.emit("Engine does not support the requested MultiPV count")

    def observe(self, generation, info):
        if generation != self.generation or not self.context:
            return
        validated = self.engine._validated_info(info)
        if not validated:
            return
        snapshot = self.collector.observe(validated, self.required)
        if snapshot:
            try:
                self.db.capture(self.context, snapshot)
            except ValueError as exc:
                self.cancel()
                self.failed.emit(str(exc))
                return
        self.updated.emit(validated)

    def message(self, generation, kind, data):
        if generation != self.generation or not self.context:
            return
        if kind in ('result', 'error'):
            context, self.context = self.context, None
            complete = all(rank in self.collector.lines for rank in range(1, self.required+1))
            status = ('completed' if complete else 'completed-incomplete') if kind == 'result' else 'failed'
            self.db.finish(context['id'], status)
            if kind == 'result':
                self.completed.emit(data)
            else:
                self.failed.emit(data['message'])

    def cancel(self):
        if self.context:
            self.db.finish(self.context['id'], 'interrupted')
            self.context = None
        self.engine.stop()

    def close(self):
        self.cancel()
        self.engine.close()


class Tournament(QObject):
    changed = Signal()
    failed = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.state = db.get('tournament')
        self.search = Search(db, self)
        self.search.completed.connect(self.result)
        self.search.failed.connect(self.error)
        self.active = False
        self.game = None
        if self.state:
            self.restore_game()

    def restore_game(self):
        index = self.state['index']
        if index >= len(self.state['games']):
            return
        item = self.state['games'][index]
        self.game = Game(item['fen'])
        self.game.id = item.setdefault('id', str(uuid4()))
        for uci in item['moves']:
            self.game.play(self.game.board.parse_uci(uci))

    def create(self, profiles, limits, games, multipv=1, checkpoint=1_000_000, maximum=None, seed=0):
        if self.active:
            raise ValueError('Pause the current match first')
        self.state = dict(id=str(uuid4()), profiles=[asdict(p) for p in profiles],
                          limits=[asdict(l) for l in limits], games=games, index=0,
                          multipv=multipv, checkpoint=checkpoint, maximum=maximum, seed=seed)
        self.restore_game()
        self.save()

    def save(self):
        self.db.put('tournament', self.state)
        self.db.put('tournament:'+self.state['id'], self.state)
        self.changed.emit()

    def resume(self):
        if not self.state or self.state['index'] >= len(self.state['games']):
            return
        self.active = True
        self.next()

    def next(self):
        if not self.active:
            return
        if self.state['index'] >= len(self.state['games']):
            self.active = False
            self.save()
            return
        item = self.state['games'][self.state['index']]
        if self.game.outcome:
            item['result'] = self.game.outcome.result
            self.state['index'] += 1
            self.restore_game()
            self.save()
            QTimer.singleShot(0, self.next)
            return
        a_turn = (self.game.board.turn == 1) == item['a_white']
        side = 0 if a_turn else 1
        try:
            self.search.start(self.game, Profile(**self.state['profiles'][side]),
                              Limit(**self.state['limits'][side]), self.state['multipv'],
                              start=self.state['checkpoint'], maximum=self.state['maximum'],
                              tournament=self.state['id'])
        except (ValueError, OSError) as exc:
            self.error(str(exc))
        self.changed.emit()

    def result(self, data):
        if not self.active:
            return
        try:
            self.game.play(self.game.board.parse_uci(data['move']))
            self.state['games'][self.state['index']]['moves'].append(data['move'])
            self.save()
            QTimer.singleShot(0, self.next)
        except (ValueError, TypeError) as exc:
            self.error(str(exc))

    def pause(self):
        self.active = False
        self.search.cancel()
        self.save()

    def error(self, text):
        self.pause()
        self.failed.emit(text)
