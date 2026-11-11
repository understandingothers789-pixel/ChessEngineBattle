"""Conservative agreement rules using the latest completed playing searches."""
import math


DEFAULT_RULE = dict(enabled=True, after_move=50, draw_cp=20, consecutive_plies=10)


def white_cp(line, turn):
    if not line or line.get('score_type') != 'cp' or line.get('bound', 'exact') != 'exact':
        return None
    value = line.get('score_value')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value * turn


def agreement(item, ply, draw_cp=50, win_cp=200):
    """The engines search alternate positions; require the last two plies."""
    scores = list(item.get('evaluations', {}).values())
    if len(scores) != 2 or {s['ply'] for s in scores} != {ply-1, ply}:
        return None
    values = [s['white_cp'] for s in scores]
    if any(v is None for v in values):
        return None
    if all(abs(v) <= draw_cp for v in values):
        return '1/2-1/2'
    if all(v >= win_cp for v in values):
        return '1-0'
    if all(v <= -win_cp for v in values):
        return '0-1'
    return None
