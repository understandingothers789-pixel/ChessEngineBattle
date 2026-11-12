"""Exploratory opening-cluster bootstrap; never a formal sequential test."""
from collections import defaultdict
from functools import lru_cache
import math
import random


def elo(score):
    return 400*math.log10(score/(1-score)) if 0 < score < 1 else (-math.inf if score == 0 else math.inf)


@lru_cache(maxsize=128)
def cluster_interval(clusters):
    if len(clusters) < 10 or len({v for c in clusters for v in c}) <= 1:
        return None
    rng = random.Random(730)
    draws = []
    for _ in range(2000):
        sample = [value for _ in clusters for value in clusters[rng.randrange(len(clusters))]]
        draws.append(sum(sample)/len(sample))
    draws.sort()
    if draws[49] == draws[1949]: return None
    return draws[49], draws[1949]


def analyze(state):
    pairs = defaultdict(list)
    identities = {}
    wins = losses = draws = 0
    for game in state['games']:
        if game['result'] == '*': continue
        result = game['result']
        score = 0.5 if result == '1/2-1/2' else float((result == '1-0') == game['a_white'])
        pairs[game['pair']].append(score)
        # Preserve repeated opening dependence. Old fixture-only rows without
        # position metadata use their pair identifier as a conservative fallback.
        identities[game['pair']] = (game.get('fen',str(game['pair'])),
            tuple(game.get('moves',[])[:game.get('opening_plies',0)]))
        wins += score == 1; losses += score == 0; draws += score == 0.5
    clusters = defaultdict(list)
    for pair, values in pairs.items():
        if len(values) == 2:
            clusters[identities[pair]].append(sum(values)/2)
    ordered = tuple(tuple(values) for _,values in sorted(clusters.items(),key=lambda item:str(item[0])))
    interval = cluster_interval(ordered)
    n = wins+losses+draws
    score = (wins+draws/2)/n if n else None
    return dict(games=n,wins=wins,losses=losses,draws=draws,score=score,
                elo=elo(score) if score is not None else None,
                interval=tuple(elo(x) for x in interval) if interval else None,
                pairs=sum(len(v) for v in clusters.values()),clusters=len(clusters),
                method='opening-cluster percentile bootstrap (2000 replicates, seed 730)',
                status='exploratory' if interval else 'insufficient independent opening information')


def summarize(state):
    r = analyze(state)
    text = f"Completed {r['games']}/{len(state['games'])} · A wins {r['wins']} · B wins {r['losses']} · draws {r['draws']}\n"
    if not r['games']: return text+'No strength estimate yet.'
    text += f"A score {r['score']:.1%} · logistic Elo estimate {r['elo']:+.1f} · draws {r['draws']/r['games']:.1%}\n"
    if r['interval']:
        text += f"Exploratory 95% paired-score Elo interval: {r['interval'][0]:+.1f} to {r['interval'][1]:+.1f}\n"
    else:
        text += 'Confidence interval unavailable: need ≥10 independent opening clusters and varying pair scores.\n'
    return text+f"Complete opening pairs: {r['pairs']} · distinct opening clusters: {r['clusters']}\n{r['method']}\nNot SPRT; repeated openings are grouped. Infinite estimates are unbounded, not precise strength measurements."


def dashboard(state):
    """Engine A perspective; only complete two-game pairs count as pairs."""
    pairs=defaultdict(list);wins=losses=draws=0
    for g in state['games']:
        if g['result']=='*':continue
        points=0.5 if g['result']=='1/2-1/2' else float((g['result']=='1-0')==g['a_white'])
        wins+=points==1;losses+=points==0;draws+=points==0.5
        pairs[g['pair']].append(points)
    scores=[sum(values) for values in pairs.values() if len(values)==2]
    n=wins+losses+draws
    estimate=elo((wins+draws/2)/n) if n else None
    return dict(wins=wins,losses=losses,draws=draws,pair_wins=sum(v>1 for v in scores),
                pair_losses=sum(v<1 for v in scores),pair_draws=sum(v==1 for v in scores),elo=estimate)
