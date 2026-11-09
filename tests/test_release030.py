from dataclasses import replace
from copy import deepcopy
import json
import sqlite3
import pytest
from PySide6.QtCore import Qt
from nocturne.core.game import Game
from nocturne_battle.model import Database,Limit,openings,schedule,position_identity
from nocturne_battle.history import Checkpoints,milestones,compare
from nocturne_battle.runtime import Search,Tournament
from nocturne_battle.experiments import build_experiment,ExperimentRunner
from nocturne_battle.game_browser import GameBrowser
from nocturne_battle.statistics import analyze
from nocturne_battle.app import Window
from test_core import info


def test_large_integer_budget_exact_transmission(qtbot,db,profile):
    limit=2**63-1
    Limit('nodes',limit).validate()
    with pytest.raises(ValueError):Limit('nodes',2**63).validate()
    with pytest.raises(ValueError):Limit('nodes',float(2**53)).validate()
    search=Search(db)
    with qtbot.waitSignal(search.completed,timeout=10000):search.start(Game(),profile,Limit('nodes',limit))
    assert '> go nodes '+str(limit) in search.engine.connection.log
    search.close()


def test_freshness_shuffled_stale_and_rank_validation():
    c=Checkpoints()
    assert c.observe(info(1_100_000,2),2) is None
    result=c.observe(info(1_100_000,1),2)
    assert result['rank_freshness'][1]['updated_on_this_observation']
    assert not result['rank_freshness'][2]['updated_on_this_observation']
    assert c.observe(info(500_000,2),2) is None
    assert c.lines[2]['nodes']==1_100_000
    bad=dict(info(),multipv=0)
    assert c.observe(bad,2) is None
    mixed=dict(info(4_500_000,1),depth=19)
    result=c.observe(mixed,2)
    assert result['lines'][2]['depth']==12
    assert not result['rank_freshness'][2]['updated_on_this_observation']


def test_milestones_never_promote_missing_first_rank():
    r=dict(requested=100,lines={'2':dict(info(rank=2),pv=['d2d4']),'1':info()})
    events=milestones([r])
    assert any('e2e4: first observed as rank 1' in text for _,text in events)
    assert not any('d2d4: first observed as rank 1' in text for _,text in events)
    missing=dict(position='p',lines={'2':dict(info(rank=2),pv=['d2d4'])})
    assert compare(missing,missing)['status']=='Missing best move'


@pytest.mark.parametrize('argument',['--crash','--illegal','--silent'])
def test_runtime_failures_are_terminal_and_cleaned(qtbot,db,profile,argument):
    profile=replace(profile,arguments=profile.arguments+[argument]);search=Search(db)
    with qtbot.waitSignal(search.failed,timeout=10000):
        search.start(Game(),profile,Limit(),silence_timeout_ms=1000)
    assert search.context is None
    assert db.export()['searches'][0]['status']=='failed'
    search.close()
    assert not search.engine.connection.alive


def test_no_info_move_is_preserved_without_fabricated_snapshots(qtbot,db,profile):
    profile=replace(profile,arguments=profile.arguments+['--no-info']);search=Search(db)
    with qtbot.waitSignal(search.completed,timeout=10000):search.start(Game(),profile,Limit())
    run=db.runs(Game(),profile)[0]
    assert run['final_result']['move']
    assert run['status']=='completed-incomplete'
    assert db.records(Game(),profile)==[]
    search.close()


def test_exact_attribution_after_interrupted_search(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--wait'])
    t=Tournament(db);t.create([p]*2,[Limit()]*2,schedule(openings(None),1))
    t.state['max_plies']=2
    t.resume();old=t.search.context['id'];t.pause();t.resume()
    qtbot.waitUntil(lambda:len(t.state['games'][0]['moves'])>=1,timeout=10000)
    t.pause()
    link=t.state['games'][0]['move_searches']['1']
    assert link['search_run_id']!=old
    assert db.search_run(old)['status']=='interrupted'
    source=db.search_run(link['search_run_id'])
    assert source['final_result']['move']==link['played_move']
    assert source['position']==link['position']
    assert db.get('tournament')['games'][0]['move_searches']==t.state['games'][0]['move_searches']
    t.search.close()


def test_original_thinking_ignores_newer_compatible_runs(qtbot,db,profile):
    db.put('profiles',[profile.__dict__])
    w=Window(db);qtbot.addWidget(w)
    w.tournament.create([profile]*2,[Limit()]*2,schedule(openings(None),1))
    w.tournament.resume()
    qtbot.waitUntil(lambda:len(w.tournament.state['games'][0]['moves'])>=1,timeout=10000)
    w.tournament.pause()
    link=w.tournament.state['games'][0]['move_searches']['1']
    game=Game();game.id=w.tournament.state['games'][0]['id']
    extra=Search(db)
    with qtbot.waitSignal(extra.completed,timeout=10000):extra.start(game,profile,Limit())
    extra.close()
    w.select_game(0);w.navigate(1);w.original_thinking()
    assert w.panels[0].run.currentData()==link['search_run_id']
    assert 'Exact played-move source' in w.status.text()
    w.close()


def test_old_database_backup_and_additive_migration(tmp_path):
    path=tmp_path/'old.sqlite'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        conn.execute('INSERT INTO settings VALUES (?,?)',('old',json.dumps({'preserved':True})))
    db=Database(path)
    assert db.get('old')=={'preserved':True}
    assert db.get('payload_schema')==3
    with sqlite3.connect(str(path)+'.pre-v3.bak') as backup:
        assert backup.execute('SELECT payload FROM settings WHERE key="old"').fetchone()
    db.close()


def test_experiment_schedule_separation_and_validation(profile):
    e=build_experiment(profile,1000000,[2,10,100],openings(None),3,42)
    a,b,c=e['conditions']
    assert a['games']==b['games']==c['games']
    assert a['games'] is not b['games']
    assert len({x['id'] for x in e['conditions']})==3
    assert [x['limits'][1]['value'] for x in e['conditions']]==[2000000,10000000,100000000]
    for x in e['conditions']:
        assert x['profiles'][0]['identity']==x['profiles'][1]['identity']
        for g,h in zip(x['games'][::2],x['games'][1::2]):assert g['a_white'] and not h['a_white']
    with pytest.raises(ValueError):build_experiment(profile,2**62,[10],openings(None),1)


def test_experiment_executes_and_recovers_without_duplicate_conditions(qtbot,db,profile):
    fen='7k/5Q2/6K1/8/8/8/8/8 w - - 0 1'
    t=Tournament(db);runner=ExperimentRunner(db,t)
    runner.create(build_experiment(profile,1000,[2,5],[fen],1))
    for c in runner.state['conditions']:c['max_plies']=2
    runner.resume();runner.resume()
    qtbot.waitUntil(lambda:not runner.active,timeout=20000)
    assert runner.state['index']==2
    assert all(c['index']==2 for c in runner.state['conditions'])
    ids={c['id'] for c in runner.state['conditions']}
    assert all(r['tournament'] in ids for r in db.export()['searches'])
    restored=ExperimentRunner(db,t)
    assert restored.state==runner.state
    t.search.close()


def test_repeated_openings_not_independent_confidence(profile):
    games=schedule(openings(None),20)
    for i,g in enumerate(games):g['result']='1-0' if i%3 else '1/2-1/2'
    result=analyze({'games':games})
    assert result['pairs']==20 and result['clusters']==1
    assert result['interval'] is None
    for g in games:g['result']='1-0' if g['a_white'] else '0-1'
    assert analyze({'games':games})['elo']==float('inf')


def test_incremental_model_filters_and_numeric_sort(qtbot,profile):
    browser=GameBrowser();qtbot.addWidget(browser)
    state=dict(id='x',profiles=[profile.__dict__]*2,games=schedule(openings(None),1000),index=0)
    browser.games.update_state(state,False)
    changed=[];resets=[]
    browser.games.dataChanged.connect(lambda a,b,*_:changed.append(a.row()))
    browser.games.modelReset.connect(lambda:resets.append(True))
    state['games'][0]['moves'].append('a2a3')
    browser.games.update_state(state,False)
    assert changed==[0] and resets==[]
    browser.sortByColumn(0,Qt.SortOrder.DescendingOrder)
    assert browser.source_row(0)==1999
    browser.proxy.setFilterFixedString('2000')
    assert browser.rowCount()==1 and browser.source_row(0)==1999


def test_heatmap_click_selects_stored_rank(qtbot,db,profile):
    search=Search(db)
    with qtbot.waitSignal(search.completed,timeout=10000):search.start(Game(),profile,Limit('nodes',9000000),5)
    search.close();db.put('profiles',[profile.__dict__])
    w=Window(db);qtbot.addWidget(w)
    v=w.candidate_views
    v.heatmap_click(0,0)
    assert w.panels[0].record['requested']==1100000//1_000_000*1_000_000
    assert w.panels[0].pv_rank.value()>=1
    panel=w.panels[0]
    panel.checkpoint.setCurrentIndex(len(panel.records))
    assert panel.record['final'] is True
    w.close()


def test_duplicate_candidates_keep_explicit_first_rank():
    record=dict(position='same',lines={'2':dict(info(rank=2)), '1':info()})
    assert compare(record,record)['status']=='Best moves agree'
    assert compare(record,record)['overlap']==[('e2e4',1,1)]


def test_degenerate_cluster_bootstrap_does_not_invent_precision():
    from nocturne_battle.statistics import cluster_interval
    assert cluster_interval(tuple((0,1) for _ in range(10))) is None


def test_adjudicated_pgn_result_matches_export(qtbot,db,profile,tmp_path,monkeypatch):
    import chess.pgn,io
    from nocturne_battle import app
    db.put('profiles',[profile.__dict__])
    w=Window(db);qtbot.addWidget(w)
    games=schedule(openings(None),1);games[0]['moves']=['a2a3'];games[0]['result']='1/2-1/2'
    w.tournament.create([profile]*2,[Limit()]*2,games)
    path=tmp_path/'result.pgn'
    monkeypatch.setattr(app.QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    w.export()
    game=chess.pgn.read_game(io.StringIO(path.read_text()))
    assert game.headers['Result']=='1/2-1/2'
    assert path.read_text().split('1/2-1/2')[1] is not None
    w.close()
