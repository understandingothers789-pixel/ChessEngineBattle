import json
from dataclasses import replace
import pytest
from nocturne_battle.app import Window
from nocturne_battle.model import Database, Limit, schedule, openings
from nocturne_battle.match_files import write_match, read_match
from nocturne_battle.match_panel import MatchCandidates
from nocturne.gui.moves import MoveText


def test_compact_display_keeps_full_data(qtbot):
    panel = MatchCandidates(MoveText(auto_fit=True));qtbot.addWidget(panel)
    info = dict(multipv=1,depth=12,nodes=1000,score_type='cp',score_value=24,score=0.24,
                pv=['g1f3','g8f6','f3g1','f6g8']*4,san=['Nf3','Nf6','Ng1','Ng8']*4)
    panel.update_line(info,1)
    assert len(panel.lines[1]['pv'])==16
    assert len(panel.rows[1][2]._items)==6
    panel.set_full(True);assert len(panel.rows[1][2]._items)==16
    panel.set_full(False);assert len(panel.rows[1][2]._items)==6


def test_portable_match_roundtrip_retains_moves_depths_and_previews(qtbot,db,profile,tmp_path):
    p=replace(profile,arguments=profile.arguments+['--depth-evolution'])
    db.put('profiles',[p.__dict__]);w=Window(db);qtbot.addWidget(w)
    w.tournament.create([p]*2,[Limit('nodes',9_000_000)]*2,schedule(openings(None),1),3)
    w.tournament.search.completed.connect(lambda _:w.tournament.pause() if w.tournament.game.cursor>=2 else None)
    w.resume();qtbot.waitUntil(lambda:w.tournament.game.cursor==2,timeout=15000)
    original_id=w.tournament.state['id'];path=tmp_path/'Tournament.cebattle'
    write_match(db,w.tournament.state,path)
    # The automatic library also keeps earlier tournaments when a new one starts.
    w.tournament.create([p]*2,[Limit('nodes',1000)]*2,schedule(openings(None),1),3)
    newer_id=w.tournament.state['id']
    w.refresh_archives()
    w.archive_selector.setCurrentIndex(w.archive_selector.findData(original_id))
    w.open_archive();w.inspect_move(1)
    assert w.tournament.state['id']==original_id and w.live_panels[0].lines
    assert db.get('tournament:'+newer_id) is not None
    target=Database(tmp_path/'second.sqlite')
    sid=read_match(target,path)
    assert sid != original_id and target.get('tournament') is None
    imported=target.get('tournament:'+sid)
    assert imported['games'][0]['moves']==w.tournament.state['games'][0]['moves']
    target.save_tournament(imported)
    restored=Window(target);qtbot.addWidget(restored)
    restored.inspect_move(2)
    assert all(len(panel.lines)==3 for panel in restored.live_panels)
    assert not restored.pause_button.isEnabled() and restored.tournament.state['review_only']
    assert restored.saved_selectors[1].count()>=5
    restored.saved_selectors[1].setCurrentIndex(1)
    assert all(line['depth']==4 for line in restored.live_panels[1].lines.values())
    restored.live_preview(1,1,2)
    assert restored.live_preview_board.preview_board is not None
    another=read_match(target,path)
    assert another != sid and len(target.archives())==2
    # A broken file cannot partially import or replace an existing match.
    payload=json.loads(path.read_text());payload['searches']=[]
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):read_match(target,path)
    assert len(target.archives())==2 and target.get('tournament')['id']==sid
    restored.close();w.close()


def test_save_button_pauses_and_restores_running_state(qtbot,db,profile,tmp_path,monkeypatch):
    from nocturne_battle.app import QFileDialog
    p=replace(profile,arguments=profile.arguments+['--wait'])
    db.put('profiles',[p.__dict__]);w=Window(db);qtbot.addWidget(w)
    w.tournament.create([p]*2,[Limit('nodes',1000)]*2,schedule(openings(None),1),3)
    w.resume()
    path=tmp_path/'My tournament.cebattle'
    def choose(*args,**kwargs):
        assert not w.tournament.active
        return str(path),''
    monkeypatch.setattr(QFileDialog,'getSaveFileName',choose)
    w.save_match_file()
    assert w.tournament.active and path.exists()
    assert json.loads(path.read_text())['tournament']['name']=='My tournament'
    w.close()


def test_interrupted_search_keeps_reported_variations(qtbot,db,profile):
    from nocturne_battle.runtime import Search
    from nocturne.core.game import Game
    p=replace(profile,arguments=profile.arguments+['--silent'])
    search=Search(db)
    search.start(Game(),p,Limit('nodes',1000),1)
    qtbot.waitUntil(lambda:search.engine.connection.phase=='search',timeout=10000)
    sid=search.context['id']
    search.observe(search.generation,dict(multipv=1,depth=4,nodes=100,score_type='cp',score_value=0,score=0,pv=['e2e4']))
    search.cancel()
    run=db.search_run(sid)
    assert run['status']=='interrupted'
    assert run['final_result']['lines']['1']['pv']==['e2e4']
    assert run['final_result']['depth_history'][0]['depth']==4
    search.close()
