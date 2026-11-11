"""Qt asynchronous orchestration on Nocturne's existing UCI controller."""
from dataclasses import asdict
from uuid import uuid4
import time
from .clocks import MatchClock
from nocturne.core.board import Outcome

from PySide6.QtCore import QObject, QTimer, Signal
from nocturne.core.game import Game
from nocturne.engine.uci_types import AnalysisLimits
from nocturne.gui.engine import EngineController

from .history import Checkpoints
from .model import Profile, Limit, executable_hash, position_identity
from .adjudication import DEFAULT_RULE, white_cp, agreement


class Search(QObject):
    started = Signal(object)
    updated = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.engine = EngineController(self)
        self.engine.set_history_capture(True)
        # Adapt only the public request's go command. All transport, readiness,
        # cancellation and PV validation continue through Nocturne unchanged.
        self._transport_request = self.engine.connection.request
        self.engine.connection.request = self._request
        self.engine.connection.status.connect(self._search_status)
        self.clock_command = None
        self.engine.connection.observation.connect(self.observe)
        self.engine.message.connect(self.message)
        self.engine.connection.configured.connect(self.configured)
        self.context = None
        self.generation = None
        self.last_completed = None
        self.watchdog = QTimer(self); self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.timed_out)
        self.render_pending = {}
        self.render_timer = QTimer(self); self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(80); self.render_timer.timeout.connect(self.flush_render)

    def start(self, game, profile, limit, multipv=1, provenance='live-playing', start=1_000_000,
              maximum=None, tournament=None, kind="continuous", silence_timeout_ms=120000, clock_command=None):
        self.cancel()
        limit.validate()
        if limit.mode == 'clock' and not clock_command:raise ValueError('Clock searches require both game clocks')
        self.clock_command=clock_command
        if kind not in ('continuous', 'independent'): raise ValueError('Unknown search kind')
        if kind == 'independent' and limit.mode != 'nodes': raise ValueError('Independent checkpoints require node limits')
        self.silence_timeout_ms = silence_timeout_ms
        self.last_completed = None
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
        self.context['kind'] = kind
        if clock_command:self.context['clock_go']=clock_command
        self.context['silence_timeout_ms'] = silence_timeout_ms
        self.context['checkpoint_start'] = start
        self.context['checkpoint_maximum'] = maximum
        with self.db.db:
            import json
            self.db.db.execute('UPDATE searches SET payload=? WHERE id=?', (json.dumps(self.context), self.context['id']))
        limits = AnalysisLimits(depth=int(limit.value) if limit.mode == 'depth' else 128,
                                seconds=float(limit.value) if limit.mode == 'movetime' else 1,
                                nodes=int(limit.value) if limit.mode == 'nodes' else None)
        try:
            if silence_timeout_ms > 0: self.watchdog.start(silence_timeout_ms)
            self.generation = self.engine.start(game, limits, external=profile.path, options=profile.options,
                arguments=profile.arguments, multipv=multipv, nodes_only=limit.mode == 'nodes',
                time_nodes_only=limit.mode == 'movetime', time_enabled=limit.mode == 'movetime')
        except Exception:
            self.db.finish(self.context['id'], 'failed')
            self.context = None
            raise

    def _request(self,generation,position,go,options,study_id='',**kwargs):
        return self._transport_request(generation,position,self.clock_command or go,options,study_id,**kwargs)

    def _search_status(self,message):
        connection=self.engine.connection
        if self.context and connection.phase == 'search' and connection.running and connection.running[0] == self.generation:
            self.started.emit(dict(self.context, started_ns=time.monotonic_ns()))

    def timed_out(self):
        if self.context:
            context = self.context
            self.cancel()
            self.db.finish(context['id'], 'failed', {'message':'No valid UCI search information or bestmove before the configured silence timeout'})
            self.failed.emit('Search silence timeout; search stopped. Resume starts a separate search.')

    def configured(self):
        connection = self.engine.connection
        if self.context and connection.phase == "idle":
            requested = self.context["multipv"]
            if requested > 1 and int(connection.confirmed.get("MultiPV", 1)) != requested:
                sid=self.context["id"]
                self.cancel()
                self.db.finish(sid,"failed",{"message":"Requested MultiPV is unsupported"})
                self.failed.emit("Engine does not support the requested MultiPV count")

    def observe(self, generation, info):
        if generation != self.generation or not self.context:
            return
        validated = self.engine._validated_info(info)
        if not validated:
            return
        if self.silence_timeout_ms > 0: self.watchdog.start(self.silence_timeout_ms)
        snapshot = self.collector.observe(validated, self.required)
        if snapshot and self.context['kind'] == 'continuous':
            try:
                self.db.capture(self.context, snapshot)
            except ValueError as exc:
                self.cancel()
                self.failed.emit(str(exc))
                return
        self.render_pending[validated['multipv']] = validated
        if not self.render_timer.isActive(): self.render_timer.start()

    def flush_render(self):
        self.render_timer.stop()
        pending, self.render_pending = self.render_pending, {}
        for _, info in sorted(pending.items()): self.updated.emit(info)

    def message(self, generation, kind, data):
        if generation != self.generation or not self.context:
            return
        if kind in ('result', 'error'):
            data=dict(data,received_ns=time.monotonic_ns())
            self.watchdog.stop()
            self.flush_render()
            context, self.context = self.context, None
            if kind == 'result':
                # Persist final ranks even when a short search never reaches a checkpoint.
                data['lines'] = dict(self.collector.lines)
            complete = all(rank in self.collector.lines for rank in range(1, self.required+1))
            status = ('completed' if complete else 'completed-incomplete') if kind == 'result' else 'failed'
            if kind == 'result' and context['kind'] == 'independent':
                lines = dict(self.collector.lines)
                actual = max((x.get('nodes', 0) for x in lines.values()), default=0)
                try:
                    self.db.capture(context, dict(requested=context['limit']['value'], actual=actual,
                        lines=lines, complete=complete, final_bestmove=data.get('move'),
                        rank_freshness=self.collector.freshness()))
                except ValueError as exc:
                    self.db.finish(context['id'], 'failed', data)
                    self.failed.emit(str(exc)); return
            self.db.finish(context['id'], status, data)
            if kind == 'result':
                self.last_completed = context | {'status':status}
                self.completed.emit(dict(data, search_run_id=context['id']))
            else:
                self.failed.emit(data['message'])

    def cancel(self):
        self.watchdog.stop()
        self.render_timer.stop(); self.render_pending.clear()
        if self.context:
            self.db.finish(self.context['id'], 'interrupted')
            self.context = None
        self.engine.stop()

    def close(self):
        self.cancel()
        self.engine.close()


class Tournament(QObject):
    changed = Signal()
    clock_changed = Signal()
    failed = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.state = db.get('tournament')
        self.search = Search(db, self)
        self.search.completed.connect(self.result)
        self.search.started.connect(self.start_clock)
        self.clock = None
        self.clock_timer=QTimer(self);self.clock_timer.setInterval(50)
        self.clock_timer.timeout.connect(self.tick_clock)
        self.search.failed.connect(self.error)
        self.active = False
        self.game = None
        if self.state:
            self.restore_game()

    def restore_game(self):
        index = self.state['index']
        if index >= len(self.state['games']):
            self.clock=None;self.game=None
            return
        item = self.state['games'][index]
        self.game = Game(item['fen'])
        self.game.id = item.setdefault('id', str(uuid4()))
        for uci in item['moves']:
            self.game.play(self.game.board.parse_uci(uci))
        self.clock=None
        limits=[Limit(**limit) for limit in self.state['limits']]
        if all(limit.mode == 'clock' for limit in limits):
            self.clock=MatchClock.restore(item['clock']) if item.get('clock') else MatchClock.create(limits,item['a_white'])
        if item['result'] != '*':self.game.declared=Outcome(item['result'],item.get('termination','Stored result'))

    def create(self, profiles, limits, games, multipv=1, checkpoint=1_000_000, maximum=None, seed=0):
        if self.active:
            raise ValueError('Pause the current match first')
        for limit in limits:limit.validate()
        if any(limit.mode == 'clock' for limit in limits) and not all(limit.mode == 'clock' for limit in limits):raise ValueError('Both engines must use clock mode together')
        self.state = dict(id=str(uuid4()), profiles=[asdict(p) for p in profiles],
                          limits=[asdict(l) for l in limits], games=games, index=0,
                          multipv=multipv, checkpoint=checkpoint, maximum=maximum, seed=seed,
                          draw_rule=dict(DEFAULT_RULE))
        self.restore_game()
        self.save()

    def save(self):
        if not self.state:
            return
        if self.clock and self.state['index'] < len(self.state['games']):
            self.state['games'][self.state['index']]['clock']=self.clock.payload()
        self.db.save_tournament(self.state)
        self.changed.emit()

    def resume(self):
        if not self.state or self.state['index'] >= len(self.state['games']):
            return
        if self.active:
            return
        self.active = True
        self.next()

    def start_clock(self,context):
        if not self.active or not self.clock:return
        if context['game'] != self.game.id:return
        self.clock.start(self.game.board.turn,now=context['started_ns'])
        self.clock_timer.start()
        self.save()
        self.clock_changed.emit()

    def forfeit(self,color):
        self.clock_timer.stop()
        sid=self.search.context['id'] if self.search.context else None
        self.search.cancel()
        if sid:self.db.finish(sid,'time-forfeit',{'message':'Clock expired'})
        draw=self.game.board.native.has_insufficient_material(color != 1)
        result='1/2-1/2' if draw else ('0-1' if color == 1 else '1-0')
        self.game.declared=Outcome(result,'Time forfeit' if not draw else 'Time expired; opponent cannot mate')
        item=self.state['games'][self.state['index']]
        item['result']=result;item['termination']=self.game.declared.reason
        self.save()
        self.clock_changed.emit()
        QTimer.singleShot(0,self.next)

    def tick_clock(self):
        if self.clock and self.clock.active is not None and self.clock.left(self.clock.active)==0:
            color=self.clock.active;self.clock.stop();self.forfeit(color)
        self.clock_changed.emit()

    def next(self):
        if not self.active or self.search.context:
            return
        if self.state['index'] >= len(self.state['games']):
            self.active = False
            self.save()
            return
        item = self.state['games'][self.state['index']]
        if self.game.cursor >= self.state.get('max_plies', 1000) and not self.game.outcome:
            self.game.agree_draw()
            item['termination'] = 'Maximum game length'
        if self.game.outcome:
            item['result'] = self.game.outcome.result
            item.setdefault('termination', self.game.outcome.reason)
            self.state['index'] += 1
            self.restore_game()
            self.save()
            QTimer.singleShot(0, self.next)
            return
        if self.clock and self.clock.left(self.game.board.turn)==0:
            self.forfeit(self.game.board.turn);return
        a_turn = (self.game.board.turn == 1) == item['a_white']
        side = 0 if a_turn else 1
        try:
            self.search.start(self.game, Profile(**self.state['profiles'][side]),
                              Limit(**self.state['limits'][side]), self.state['multipv'],
                              start=self.state['checkpoint'], maximum=self.state['maximum'],
                              tournament=self.state['id'],silence_timeout_ms=0 if self.clock else self.state.get('silence_timeout_ms',120000),
                              clock_command=self.clock.uci() if self.clock else None)
        except (ValueError, OSError) as exc:
            self.error(str(exc))
        self.changed.emit()

    def result(self, data):
        if not self.active:
            return
        try:
            context = self.search.last_completed
            if not context or data.get('search_run_id') != context['id']:
                raise ValueError('Move has no verified originating search')
            if context['game'] != self.game.id or context['position'] != position_identity(self.game):
                raise ValueError('Search result belongs to a different game or position')
            timing={}
            if self.clock:
                before=self.clock.payload()
                flag,elapsed=self.clock.stop(now=data['received_ns'],add_increment=True)
                self.clock_timer.stop()
                if flag is not None:self.forfeit(flag);return
                timing=dict(clock_before=before,clock_after=self.clock.payload(),elapsed_ns=elapsed)
            ply = self.game.cursor + 1
            turn = self.game.board.turn
            fullmove = self.game.board.native.fullmove_number
            link = dict(game=self.game.id, ply=ply, position=context['position'],
                        profile=context['profile'], search_run_id=context['id'], limit=context['limit'],
                        bestmove=data['move'], played_move=data['move'], status=context['status'],**timing)
            self.game.play(self.game.board.parse_uci(data['move']))
            item = self.state['games'][self.state['index']]
            item['moves'].append(data['move'])
            item.setdefault('move_searches', {})[str(ply)] = link
            side = '0' if (turn == 1) == item['a_white'] else '1'
            line = data.get('lines', {}).get(1, data.get('lines', {}).get('1'))
            item.setdefault('evaluations', {})[side] = dict(
                ply=ply, white_cp=white_cp(line, turn), search_run_id=context['id'])
            rule = self.state.get('draw_rule', DEFAULT_RULE)
            qualifies = (rule['enabled'] and fullmove > rule['after_move'] and
                         agreement(item, ply, rule['draw_cp']) == '1/2-1/2')
            item['draw_streak'] = item.get('draw_streak', 0) + 1 if qualifies else 0
            if not self.game.outcome and item['draw_streak'] >= rule['consecutive_plies']:
                self.adjudicate('1/2-1/2',
                    f"Draw by evaluation agreement (both engines within ±{rule['draw_cp']/100:g} pawns "
                    f"for {rule['consecutive_plies']} consecutive plies after move {rule['after_move']})")
                return
            self.save()
            QTimer.singleShot(0, self.next)
        except (ValueError, TypeError) as exc:
            self.error(str(exc))

    def adjudicate(self, result=None, reason=None, draw_cp=50, win_cp=200):
        if not self.state or not self.game or self.game.outcome:
            raise ValueError('There is no unfinished current game to adjudicate.')
        item = self.state['games'][self.state['index']]
        if result is None:
            result = agreement(item, self.game.cursor, draw_cp, win_cp)
            if result is None:
                raise ValueError('No evaluation agreement: both engines need exact scores from the last two completed plies, within the draw threshold or favoring the same side at the win threshold.')
            reason = (f"Draw by evaluation agreement (both engines within ±{draw_cp/100:g} pawns)"
                      if result == '1/2-1/2' else
                      f"Win by evaluation agreement (both engines favor the winner by at least {win_cp/100:g} pawns)")
        if result not in ('1/2-1/2', '1-0', '0-1'):
            raise ValueError('Invalid adjudicated result')
        self.clock_timer.stop()
        if self.clock:self.clock.stop()
        self.search.cancel()
        self.game.declared = Outcome(result, reason or 'Manual adjudication')
        item['result'] = result
        item['termination'] = self.game.declared.reason
        item['adjudication'] = dict(ply=self.game.cursor, evaluations=dict(item.get('evaluations', {})))
        self.save()
        self.clock_changed.emit()
        if self.active:QTimer.singleShot(0, self.next)

    def pause(self):
        self.active = False
        self.clock_timer.stop()
        if self.clock:
            flag,_=self.clock.stop()
            if flag is not None:self.forfeit(flag)
        self.search.cancel()
        self.save()

    def error(self, text):
        self.pause()
        self.failed.emit(text)
