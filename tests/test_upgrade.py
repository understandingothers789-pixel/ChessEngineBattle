from dataclasses import replace
import json
import pytest
from PySide6.QtWidgets import QSpinBox
from nocturne.core.game import Game
from nocturne_battle.app import Window, ProfileDialog
from nocturne_battle.model import Limit, openings, schedule, parse_budget, position_identity
from nocturne_battle.runtime import Search, Tournament
from nocturne_battle.history import select_checkpoint, milestones
from nocturne_battle.statistics import summarize


def run(qtbot, db, profile, **kwargs):
    search = Search(db)
    with qtbot.waitSignal(search.completed,timeout=10000):
        search.start(Game(),profile,Limit('nodes',9_000_000),5,'post-game',**kwargs)
    search.close()
    return db.runs(Game(),profile)[0]


def test_visual_editor_without_raw_json(qtbot,profile):
    dialog = ProfileDialog(existing=profile); qtbot.addWidget(dialog)
    assert not dialog.raw_enabled.isChecked()
    assert dialog.connection.phase == 'closed'
    dialog.validate()
    qtbot.waitUntil(lambda: dialog.discovered is not None,timeout=10000)
    assert isinstance(dialog.option_widgets['Hash'],QSpinBox)
    dialog.option_widgets['Hash'].setValue(128)
    dialog.name.setText('Independent profile')
    dialog.save()
    assert dialog.profile.options['Hash'] == 128
    assert dialog.profile.name == 'Independent profile'
    assert dialog.profile.id != profile.id


def test_runs_remain_separate_and_final_bestmove_is_saved(qtbot,db,profile):
    first = run(qtbot,db,profile)
    second = run(qtbot,db,profile)
    assert first['id'] != second['id']
    assert second['final_result']['move'] == 'a2a3'
    db.put('profiles',[profile.__dict__])
    window = Window(db); qtbot.addWidget(window)
    panel = window.panels[0]
    assert panel.run.count() == 2
    assert len(panel.records) == 3
    assert {r['id'] for r in panel.records} == {second['id']}
    panel.run.setCurrentIndex(1)
    assert {r['id'] for r in panel.records} == {first['id']}
    assert {r['id'] for r in window.graph.series[0]} == {first['id']}
    window.close()


def test_independent_final_budget_and_partial_ranks(qtbot,db,profile):
    profile = replace(profile,arguments=profile.arguments+['--incomplete'])
    result = run(qtbot,db,profile,kind='independent')
    records = db.records(Game(),profile)
    assert len(records) == 1
    assert records[0]['requested'] == 9_000_000
    assert records[0]['actual'] == 8_100_000
    assert records[0]['kind'] == 'independent'
    assert records[0]['complete'] is False
    assert records[0]['final_bestmove'] == result['final_result']['move']
    assert len(records[0]['lines']) == 1


def test_logarithmic_approximation():
    # 3 vs 12: 6 is exactly halfway in log space; 7 is nearer 12.
    records = [{'requested':3},{'requested':12}]
    assert select_checkpoint(records,7)[0]['requested'] == 12


@pytest.mark.parametrize('text,expected',[('100M',100000000),('1B',1000000000),('1,024,000',1024000),('1.024B',1024000000)])
def test_budget_units(text,expected):
    assert parse_budget(text) == expected


def test_resume_is_idempotent(qtbot,db,profile):
    profile = replace(profile,arguments=profile.arguments+['--wait'])
    tournament = Tournament(db)
    tournament.create([profile]*2,[Limit()]*2,schedule(openings(None),1))
    tournament.resume()
    sid = tournament.search.context['id']
    tournament.resume()
    assert tournament.search.context['id'] == sid
    assert len(db.export()['searches']) == 1
    tournament.pause(); tournament.search.close()


def test_opening_move_path_survives_pair_and_restore(db,profile,tmp_path):
    path = tmp_path/'suite.pgn'
    path.write_text('[Opening "Repetition"]\n\n1. Nf3 Nf6 2. Ng1 Ng8 *')
    suite = openings(path)
    pairs = schedule(suite,1)
    assert pairs[0]['moves'] == ['g1f3','g8f6','f3g1','f6g8']
    assert pairs[0]['moves'] == pairs[1]['moves']
    assert pairs[0]['opening_name'] == 'Repetition'
    tournament = Tournament(db)
    tournament.create([profile]*2,[Limit()]*2,pairs)
    assert tournament.game.cursor == 4
    assert len(tournament.game.board.native.move_stack) == 4
    assert position_identity(tournament.game) != position_identity(Game(str(suite[0])))
    tournament.search.close()


def test_archive_browser_restores_profile_and_games(qtbot,db,profile):
    db.put('profiles',[profile.__dict__])
    tournament = Tournament(db)
    tournament.create([profile]*2,[Limit()]*2,schedule(openings(None),1))
    old = tournament.state['id']
    tournament.create([profile]*2,[Limit()]*2,schedule(openings(None),2))
    tournament.search.close()
    window = Window(db); qtbot.addWidget(window)
    window.archive_selector.setCurrentIndex(window.archive_selector.findData(old))
    window.open_archive()
    assert window.tournament.state['id'] == old
    assert window.games_table.rowCount() == 2
    window.table_game(1,0)
    assert not window.follow_live
    window.close()


def test_live_info_does_not_mutate_historical_candidates(qtbot,db,profile):
    run(qtbot,db,profile)
    db.put('profiles',[profile.__dict__])
    window = Window(db); qtbot.addWidget(window)
    window.tournament.create([profile]*2,[Limit()]*2,schedule(openings(None),1))
    historical = json.dumps(window.panels[0].record, sort_keys=True)
    window.tournament.active = True
    window.follow_live = False
    line = dict(window.panels[0].panel.lines[1]); line['score_value'] = 999
    window.live_info(line)
    assert window.live_panels[0].lines[1]['score_value'] == 999
    assert json.dumps(window.panels[0].record,sort_keys=True) == historical
    window.tournament.active = False
    window.close()


def test_pv_divergence_is_highlighted_in_move_widgets(qtbot,db,profile):
    run(qtbot,db,profile)
    db.put('profiles',[profile.__dict__])
    window = Window(db); qtbot.addWidget(window)
    window.panels[1].pv_rank.setValue(2)
    assert window.panels[0].panel.rows[1][2].extraSelections()
    assert window.panels[1].panel.rows[2][2].extraSelections()
    assert 'Shared candidate' in window.panels[0].panel.rows[1][1].text()
    window.close()


def test_milestones_observed_language():
    records = [dict(requested=100,lines={'1':{'pv':['e2e4']}}), dict(requested=200,lines={'1':{'pv':['d2d4']}})]
    events = milestones(records)
    assert any('first observed' in text for _,text in events)
    assert any('no longer' in text for _,text in events)


def test_paired_statistics_uncertainty():
    games = []
    for pair in range(20):
        games.extend([dict(pair=pair,a_white=True,result='1-0' if pair%2 else '1/2-1/2'),
                      dict(pair=pair,a_white=False,result='0-1' if pair%2 else '1/2-1/2')])
    text = summarize({'games':games})
    assert '95% paired-score' in text
    assert 'Complete opening pairs: 20' in text


def test_embedded_nnue_default_is_not_mistaken_for_external_file(qtbot,profile):
    from nocturne.engine.uci_types import UciOption
    dialog = ProfileDialog(existing=profile); qtbot.addWidget(dialog)
    dialog.validation = (dialog.path.text(), dialog.args.text())
    dialog.discover(dict(name='Embedded network engine',options={
        'Threads':UciOption('Threads','spin','1',1,16),
        'Hash':UciOption('Hash','spin','64',1,1024),
        'EvalFile':UciOption('EvalFile','string','embedded-nonexistent.nnue')}))
    dialog.save()
    assert dialog.profile is not None
    assert 'EvalFile' not in dialog.profile.options
    assert dialog.profile.networks == {}
