"""Doubling capture extracted from Nocturne AnalysisHistory.observe (5f9c695).

Preserve its highest-crossed-only rule. Snapshots are observations, not exact
independent node-limited results. GPL-3.0-or-later; Nocturne Chess contributors.
"""
from copy import deepcopy
import math


class Checkpoints:
    def __init__(self, start=1_000_000, maximum=None):
        if start < 1 or (maximum is not None and maximum < start):
            raise ValueError('Invalid checkpoint bounds')
        self.next_nodes = start
        self.maximum = maximum
        self.lines = {}

    def observe(self, info, required):
        self.lines[info['multipv']] = deepcopy(info)
        # Nocturne's window waits for every required rank before advancing history.
        if not all(rank in self.lines for rank in range(1, required + 1)):
            return None
        nodes = info.get('nodes', 0)
        crossed = None
        while nodes >= self.next_nodes and (self.maximum is None or self.next_nodes <= self.maximum):
            crossed = self.next_nodes
            self.next_nodes *= 2
        if crossed is None:
            return None
        lines = deepcopy(self.lines)
        return dict(requested=crossed, actual=nodes, lines=lines,
                    complete=all(rank in lines for rank in range(1, required + 1)))


def select_checkpoint(records, target):
    if not records:
        return None, 'unavailable'
    record = min(records, key=lambda r: abs(math.log(r['requested'] / target)))
    return record, 'exact' if record['requested'] == target else 'approximate'


def compare(a, b, rank_a=1, rank_b=1):
    if not a or not b:
        return {'status': 'Missing analysis'}
    if a['position'] != b['position']:
        raise ValueError('Cannot compare different positions')
    left = [x['pv'][0] for _, x in sorted(a['lines'].items(), key=lambda x: int(x[0])) if x['pv']]
    right = [x['pv'][0] for _, x in sorted(b['lines'].items(), key=lambda x: int(x[0])) if x['pv']]
    apv = a['lines'].get(str(rank_a), a['lines'].get(rank_a, {})).get('pv', [])
    bpv = b['lines'].get(str(rank_b), b['lines'].get(rank_b, {})).get('pv', [])
    shared = 0
    for x, y in zip(apv, bpv):
        if x != y:
            break
        shared += 1
    return dict(status=('Best moves agree' if left and right and left[0] == right[0]
                        else 'Different best moves' if left and right else 'Missing best move'),
                overlap=[(m, left.index(m)+1, right.index(m)+1) for m in left if m in right],
                only_a=[m for m in left if m not in right], only_b=[m for m in right if m not in left],
                shared_prefix=shared, divergence=shared+1 if apv[shared:] or bpv[shared:] else None)


def milestones(records):
    """Describe first recorded changes within one explicitly selected search."""
    events, seen, previous = [], set(), None
    for record in sorted(records, key=lambda r: r['requested']):
        candidates = [x['pv'][0] for x in record['lines'].values() if x.get('pv')]
        for move in candidates:
            if move not in seen:
                events.append((record['requested'], f'{move}: first observed'))
                seen.add(move)
        if candidates and previous and candidates[0] != previous[0]:
            events.append((record['requested'], f'{candidates[0]}: first observed as preferred after {previous[0]}'))
        if previous:
            for move in previous:
                if move not in candidates:
                    events.append((record['requested'], f'{move}: no longer in recorded candidates'))
        previous = candidates
    return events
