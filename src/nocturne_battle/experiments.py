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

    def resume(self):
        if self.active or not self.state: return
        if self.tournament.active: raise ValueError('Another tournament is running')
        self.active = True
        self.next()

    def next(self):
        if not self.active: return
        if self.state['index'] >= len(self.state['conditions']):
            self.active = False; self.save(); return
        condition = self.state['conditions'][self.state['index']]
        self.tournament.state = deepcopy(condition)
        self.tournament.restore_game()
        self.tournament.save()
        self.tournament.resume()

    def observe(self):
        if not self.state or not self.tournament.state: return
        for i,condition in enumerate(self.state['conditions']):
            if condition['id'] == self.tournament.state['id']:
                self.state['conditions'][i] = deepcopy(self.tournament.state)
                if self.active and i == self.state['index'] and self.tournament.state['index'] >= len(condition['games']):
                    self.state['index'] += 1
                    QTimer.singleShot(0,self.next)
                self.save(); break

    def pause(self):
        self.active = False
        if self.tournament.active: self.tournament.pause()
        self.save()
