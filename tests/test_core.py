from dataclasses import replace
import json
import pytest
from nocturne.core.game import Game
from nocturne.engine.uci_types import parse_info, score_label
from nocturne_battle.history import Checkpoints, compare, select_checkpoint
from nocturne_battle.model import Database, Limit, openings, position_identity, schedule


def info(nodes=1_100_000, rank=1):
    return parse_info(f'info depth 12 seldepth 15 multipv {rank} score cp 25 nodes {nodes} time 20 nps 500 pv e2e4 e7e5')


def test_doubling_skip_immutable_and_unbounded():
    collector = Checkpoints()
    assert collector.observe(info(500_000), 5) is None
    first = collector.observe(info(), 1)
    assert first['requested'] == 1_000_000 and first['actual'] == 1_100_000
    assert first['complete']
    later = collector.observe(info(5_000_000), 1)
    assert later['requested'] == 4_000_000
    assert collector.next_nodes == 8_000_000
    assert first['lines'][1]['nodes'] == 1_100_000
    assert collector.observe(info(2_100_000_000), 1)['requested'] == 2_048_000_000


def test_config_bounds():
    with pytest.raises(ValueError):
        Checkpoints(0)
    c = Checkpoints(10, 20)
    assert c.observe(info(30), 1)['requested'] == 20
    assert c.observe(info(100), 1) is None


def test_exact_approximate_unavailable():
    rows = [{'requested': 8}, {'requested': 64}]
    assert select_checkpoint(rows, 64)[1] == 'exact'
    assert select_checkpoint(rows, 80) == (rows[1], 'approximate')
    assert select_checkpoint([], 80) == (None, 'unavailable')


def test_persistence_profiles_history_and_provenance(db, profile):
    game = Game()
    context = db.begin(game, profile, Limit(), 1, 'live-playing')
    db.capture(context, Checkpoints().observe(info(), 1))
    db.finish(context['id'], 'completed')
    assert db.records(game, replace(profile, options={'Threads': 2})) == []
    assert db.records(game, profile, 5) == []
    path = db.path
    db.close()
    fresh = Database(path)
    records = fresh.records(game, profile)
    assert records[0]['provenance'] == 'live-playing'
    assert records[0]['status'] == 'completed'
    assert records[0]['lines']['1']['pv'] == ['e2e4', 'e7e5']
    fresh.close()


def test_exact_position_and_same_position_guard():
    game = Game()
    other = Game('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')
    assert position_identity(game) != position_identity(other)
    with pytest.raises(ValueError):
        compare({'position':'a'}, {'position':'b'})
    a = dict(position='same', lines={'1':info(), '2':dict(info(rank=2), pv=['d2d4'])})
    b = dict(position='same', lines={'1':dict(info(),pv=['d2d4']), '2':info(rank=2)})
    result = compare(a,b)
    assert result['status'] == 'Different best moves'
    assert result['overlap'] == [('e2e4',1,2), ('d2d4',2,1)]
    assert result['divergence'] == 1


def test_opening_pairs_seed_and_validation(tmp_path):
    epd = tmp_path/'suite.epd'
    epd.write_text('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - id "start";\n')
    fens = openings(epd)
    rows = schedule(fens, 100, seed=42, randomized=True)
    assert len(rows) == 200
    for a,b in zip(rows[::2], rows[1::2]):
        assert a['fen'] == b['fen'] and a['a_white'] and not b['a_white']
    assert rows == schedule(fens,100,42,True)
    pgn = tmp_path/'suite.pgn'
    pgn.write_text('[Result "*"]\n\n1. e4 e5 *')
    assert openings(pgn)[0].split()[1] == 'w'


@pytest.mark.parametrize('limit',[Limit('nodes',10**15),Limit('depth',20),Limit('movetime',0.1)])
def test_valid_limits(limit):
    limit.validate()


@pytest.mark.parametrize('limit',[Limit('nodes',0),Limit('depth',129),Limit('clock',2)])
def test_invalid_limits(limit):
    with pytest.raises(ValueError):
        limit.validate()


def test_scores_preserve_mate_bound_perspective():
    line = parse_info('info score mate -3 upperbound pv e2e4')
    assert score_label(line,-1) == '≥ #3'
    assert line['score_type'] == 'mate'


def test_interruption_and_storage_ceiling(db, profile):
    context = db.begin(Game(),profile,Limit(),1,'post-game')
    db.recover()
    assert db.export()['searches'][0]['status'] == 'interrupted'
    db.max_bytes = 1
    with pytest.raises(ValueError,match='storage limit'):
        db.capture(context,Checkpoints().observe(info(),1))
    assert json.loads(json.dumps(db.export()))['searches'][0]['id'] == context['id']


def test_complete_rank_gate_matches_upstream(qtbot):
    from nocturne.gui.analysis_history import AnalysisHistory
    upstream = AnalysisHistory(lambda: False)
    qtbot.addWidget(upstream)
    upstream.position('same', Game().board.fen(), 1)
    extracted = Checkpoints()
    for nodes in [1_100_000,5_000_000,8_100_000,17_000_000]:
        lines = {1: info(nodes)}
        upstream.observe(1, lines, nodes)
        captured = extracted.observe(info(nodes),1)
        assert captured['requested'] == max(upstream.checkpoints)
        assert captured['actual'] == upstream.checkpoints[captured['requested']][0]
        assert captured['lines'] == upstream.checkpoints[captured['requested']][1]
    upstream.close()


def test_external_network_content_is_part_of_profile_identity(profile,tmp_path):
    network = tmp_path/'network.nnue'
    network.write_bytes(b'first')
    original = replace(profile,options={'EvalFile':str(network)})
    original.networks = original.network_files()
    network.write_bytes(b'second')
    updated = replace(original,networks=original.network_files())
    assert updated.fingerprint() != original.fingerprint()
