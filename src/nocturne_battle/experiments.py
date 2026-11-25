"""Persistent sequential node-scaling conditions with identical paired schedules."""
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4
from PySide6.QtCore import QObject, QTimer, Signal
from .model import Limit, schedule


def build_experiment(profile, base, ratios, fens, pairs, seed=0, multipv=1, checkpoint=1_000_000):
    Limit('nodes',base).validate()
    if not ratios or len(set(ratios)) != len(ratios) or not 1 <= multipv <= 5:
        raise ValueError('Choose distinct positive integer ratios and MultiPV 1–5')
    eid = str(uuid4())
    template = schedule(fens,pairs,seed,True)
    conditions = []
    for ratio in ratios:
        if type(ratio) is not int or ratio < 1: raise ValueError('Ratios must be positive integers')
        Limit('nodes',base*ratio).validate()
        conditions.append(dict(id=str(uuid4()),experiment=eid,ratio=ratio,
            profiles=[asdict(profile),asdict(profile)],limits=[dict(mode='nodes',value=base),dict(mode='nodes',value=base*ratio)],
            games=deepcopy(template),index=0,multipv=multipv,checkpoint=checkpoint,maximum=None,seed=seed))
    return dict(id=eid,conditions=conditions,index=0,seed=seed,base=base,
                statistics_method='opening-cluster percentile bootstrap; exploratory, not sequential testing',label='Exploratory node-budget scaling; not a wall-clock benchmark')


class ExperimentRunner(QObject):
    changed = Signal()

    def __init__(self, db, tournament):
        super().__init__(tournament)
        self.db, self.tournament = db,tournament
        self.state = db.get('scaling_experiment')
        self.active = False
        tournament.changed.connect(self.observe)
        tournament.failed.connect(lambda _: self.pause())

    def save(self):
        if self.state:
            self.db.put('scaling_experiment',self.state)
            self.db.put('experiment:'+self.state['id'],self.state)
        self.changed.emit()

    def create(self, experiment):
        if self.tournament.active: raise ValueError('Pause the current match first')
        self.active = False
        self.state = experiment
        for condition in experiment['conditions']:
            self.db.put('tournament:'+condition['id'],condition)
        self.save()

    def can_append(self):
        return bool(self.state and self.state.get('kind') == 'mixed' and
                    not self.state.get('started') and not self.tournament.active)

    def enqueue(self, condition, *, replace=False):
        if self.active or self.tournament.active:
            raise ValueError('Pause the current match before editing the experiment queue.')
        if not replace and self.state and not self.can_append():
            raise ValueError('Start a new queue to add different match conditions.')
        if replace or not self.state:
            self.create(dict(id=str(uuid4()), kind='mixed', label='Mixed match experiment',
                             index=0, conditions=[]))
        condition['experiment'] = self.state['id']
        condition['name'] = f"Condition {len(self.state['conditions']) + 1} · {condition['name']}"
        self.state['conditions'].append(condition)
        self.db.put('tournament:' + condition['id'], condition)
        self.save()

    def owns_current_condition(self):
        if not self.state or not self.tournament.state:
            return False
        index = self.state['index']
        conditions = self.state['conditions']
        return index < len(conditions) and conditions[index]['id'] == self.tournament.state['id']

    def resume(self):
        if self.active or not self.state or not self.state['conditions']:
            return
        if self.tournament.active:
            raise ValueError('Another tournament is running')
        self.active = True
        self.state['started'] = True
        self.next()

    def next(self):
        if not self.active or self.tournament.active:
            return
        conditions = self.state['conditions']
        while self.state['index'] < len(conditions):
            index = self.state['index']
            condition = conditions[index]
            # The tournament archive can be newer if the app closed between
            # committing a move and saving the queue's progress.
            archived = self.db.get('tournament:' + condition['id'])
            if archived and (archived['index'] > condition['index'] or
                             (archived['index'] == condition['index'] and archived['index'] < len(archived['games']) and
                              len(archived['games'][archived['index']]['moves']) > len(condition['games'][condition['index']]['moves']))):
                condition = conditions[index] = archived
            if condition['index'] < len(condition['games']):
                self.tournament.load_new(deepcopy(condition))
                self.tournament.resume()
                return
            self.state['index'] += 1
        self.active = False
        self.save()

    def observe(self):
        if not self.state or not self.tournament.state:
            return
        match = self.tournament.state
        for index, condition in enumerate(self.state['conditions']):
            if condition['id'] != match['id']:
                continue
            self.state['conditions'][index] = deepcopy(match)
            if (self.active and index == self.state['index'] and not self.tournament.active
                    and match['index'] >= len(match['games'])):
                self.state['index'] += 1
                QTimer.singleShot(0, self.next)
            self.save()
            return
        if self.active:
            self.active = False
            self.save()

    def pause(self):
        owned = self.owns_current_condition()
        self.active = False
        if owned and self.tournament.active:
            self.tournament.pause()
        self.save()
