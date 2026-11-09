"""Paired-opening uncertainty: normal interval on independent pair scores.

Games within a color-reversed pair are kept together. This descriptive model is
not SPRT and is unreliable for very small samples or all-identical pair scores.
"""
import math
import statistics


def summarize(state):
    pairs = {}
    wins = losses = draws = 0
    for game in state['games']:
        result = game['result']
        if result == '*':
            continue
        score = 0.5 if result == '1/2-1/2' else float((result == '1-0') == game['a_white'])
        pairs.setdefault(game['pair'], []).append(score)
        wins += score == 1; losses += score == 0; draws += score == 0.5
    n = wins+losses+draws
    text = f'Completed {n}/{len(state["games"])} · A wins {wins} · B wins {losses} · draws {draws}\n'
    if not n:
        return text+'No strength estimate yet.'
    score = (wins+draws/2)/n
    elo = lambda p: 400*math.log10(p/(1-p)) if 0 < p < 1 else (-math.inf if p == 0 else math.inf)
    text += f'A score {score:.1%} · logistic Elo estimate {elo(score):+.1f}\n'
    paired = [sum(values)/2 for values in pairs.values() if len(values) == 2]
    if len(paired) >= 10 and len(set(paired)) > 1:
        mean = statistics.mean(paired)
        margin = 1.96*statistics.stdev(paired)/math.sqrt(len(paired))
        text += f'Approximate 95% paired-score Elo interval: {elo(max(0,mean-margin)):+.1f} to {elo(min(1,mean+margin)):+.1f}\n'
    else:
        text += 'Confidence interval unavailable: need ≥10 complete, varying pair scores.\n'
    text += f'Complete opening pairs: {len(paired)}. Draw-heavy results do not establish a definitive strength difference.\n'
    for pair, scores in sorted(pairs.items()):
        text += f'Pair {pair+1}: A scored {sum(scores):g}/{len(scores)}\n'
    return text
