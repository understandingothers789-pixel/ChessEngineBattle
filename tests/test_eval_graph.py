from nocturne_battle.eval_graph import MoveEvaluationGraph, scale_for


def test_scale_includes_extremes_and_resolves_small_values():
    limit, step = scale_for([0.04, -0.12, 0.23])
    assert 0.25 <= limit <= 0.5
    assert 0 < step <= limit
    assert scale_for([8.3, -1])[0] >= 8.3


def test_graph_uses_search_position_and_preserves_gaps(qtbot):
    class DB:
        def search_run(self, key):
            if key == 'missing': return None
            return {'fen': '8/8/8/8/8/8/8/8 b - - 0 19', 'final_result': {'lines': {'1': {'score_type': 'cp', 'score_value': 70}}}}
    graph = MoveEvaluationGraph(); qtbot.addWidget(graph)
    graph.load({'moves': ['x'] * 4, 'a_white': True, 'move_searches': {'3': {'search_run_id': 'b'}, '4': {'search_run_id': 'missing'}}}, DB(), 3)
    assert graph.points[1] == [(3, -0.7, 19, -1)]
    graph.resize(800, 350); graph.show(); qtbot.waitExposed(graph)
    assert graph.grab().width() == 800
