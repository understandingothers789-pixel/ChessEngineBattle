"""Find the greatest advantage supported by both completed move searches."""
from .adjudication import white_cp


def strongest_agreement(item, db):
    moves = {}
    for link in item.get('move_searches', {}).values():
        run = db.search_run(link['search_run_id'])
        if not run:
            continue
        fen = run['fen'].split()
        turn = 1 if fen[1] == 'w' else -1
        lines = run.get('final_result', {}).get('lines', {})
        score = white_cp(lines.get('1', lines.get(1)), turn)
        if score is None:
            continue
        side = 0 if (turn == 1) == item['a_white'] else 1
        moves.setdefault(int(fen[5]), {})[side] = score
    best = None
    for move, scores in sorted(moves.items()):
        if len(scores) != 2:
            continue
        a, b = scores[0], scores[1]
        value = min(a, b) if a >= 0 and b >= 0 else max(a, b) if a <= 0 and b <= 0 else 0
        if best is None or abs(value) > abs(best[0]):
            best = (value, move, a, b)
    return best
