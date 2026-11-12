from nocturne_battle.draw_evaluation import strongest_agreement


class DB:
    def __init__(self, runs): self.runs = runs
    def search_run(self, key): return self.runs.get(key)


def test_draw_peak_uses_smaller_agreed_score_and_white_perspective():
    def run(move, side, score):
        return {'fen': f'8/8/8/8/8/8/8/8 {side} - - 0 {move}',
                'final_result': {'lines': {'1': {'score_type': 'cp', 'score_value': score}}}}
    runs = {'a': run(12, 'w', 500), 'b': run(12, 'b', -70),
            'c': run(13, 'w', -200), 'd': run(13, 'b', 50),
            'e': run(14, 'w', 900)}
    item = {'a_white': True, 'move_searches': {str(i): {'search_run_id': key} for i, key in enumerate(runs)}}
    assert strongest_agreement(item, DB(runs)) == (70, 12, 500, 70)
