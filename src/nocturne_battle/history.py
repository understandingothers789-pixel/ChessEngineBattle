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
        self.sequence = 0
        self.observations = {}

    def observe(self, info, required):
        rank = info.get('multipv')
        if type(rank) is not int or not 1 <= rank <= required or not info.get('pv'):
            return None
        # Reject an older observation for a rank; other ranks can legitimately
        # have lower nodes or depths. Equal-node observations remain observable.
        previous = self.lines.get(rank)
        if previous and (info.get('nodes',0) < previous.get('nodes',0) or
                         (info.get('nodes',0) == previous.get('nodes',0) and
                          info.get('depth',0) < previous.get('depth',0))):
            return None
        self.sequence += 1
        self.observations[rank] = self.sequence
        self.lines[rank] = deepcopy(info)
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
                    complete=all(rank in lines for rank in range(1, required + 1)), rank_freshness=self.freshness())

    def freshness(self):
        return {rank:dict(observation_sequence=self.observations[rank],
                          updated_on_this_observation=self.observations[rank] == self.sequence,
                          nodes=line.get('nodes',0), depth=line.get('depth',0))
                for rank,line in self.lines.items()}


def ranked(lines):
    result = []
    for key,line in lines.items():
        try: rank = int(key)
        except (TypeError,ValueError): continue
        if 1 <= rank <= 5 and line.get('multipv',rank) == rank and line.get('pv'):
            result.append((rank,line))
    return sorted(result,key=lambda item:item[0])


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
    left_ranks = {}
    for rank,line in ranked(a['lines']):left_ranks.setdefault(line['pv'][0],rank)
    left = list(left_ranks)
    right_ranks = {}
    for rank,line in ranked(b['lines']):right_ranks.setdefault(line['pv'][0],rank)
    right = list(right_ranks)
    apv = a['lines'].get(str(rank_a), a['lines'].get(rank_a, {})).get('pv', [])
    bpv = b['lines'].get(str(rank_b), b['lines'].get(rank_b, {})).get('pv', [])
    shared = 0
    for x, y in zip(apv, bpv):
        if x != y:
            break
        shared += 1
    return dict(status=('Best moves agree' if 1 in left_ranks.values() and 1 in right_ranks.values() and next(m for m,r in left_ranks.items() if r == 1) == next(m for m,r in right_ranks.items() if r == 1)
                        else 'Different best moves' if 1 in left_ranks.values() and 1 in right_ranks.values() else 'Missing best move'),
                overlap=[(m, left_ranks[m], right_ranks[m]) for m in left if m in right],
                only_a=[m for m in left if m not in right], only_b=[m for m in right if m not in left],
                shared_prefix=shared, divergence=shared+1 if apv[shared:] or bpv[shared:] else None)


def milestones(records):
    """Describe first recorded changes within one explicitly selected search."""
    events, seen, previous = [], set(), None
    previous_best = None
    promoted = set()
    for record in sorted(records, key=lambda r: r['requested']):
        ordered = ranked(record['lines'])
        candidates = [x['pv'][0] for _,x in ordered]
        best = next((x['pv'][0] for rank,x in ordered if rank == 1),None)
        for move in candidates:
            if move not in seen:
                events.append((record['requested'], f'{move}: first observed'))
                seen.add(move)
        if best and best != previous_best:
            word = 'first observed as rank 1' if best not in promoted else 'observed returning to rank 1'
            events.append((record['requested'], f'{best}: {word}')); promoted.add(best)
        if previous:
            for move in previous:
                if move not in candidates:
                    events.append((record['requested'], f'{move}: no longer in recorded candidates'))
        previous = candidates
        previous_best = best
    return events
