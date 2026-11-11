from dataclasses import replace
import pytest
from nocturne.core.game import Game
from nocturne_battle.adjudication import agreement, white_cp
from nocturne_battle.model import Limit, schedule
from nocturne_battle.runtime import Tournament, Search
from nocturne_battle.app import Window


@pytest.mark.parametrize('a,b,result', [(20,-20,'1/2-1/2'), (21,0,None),
    (200,250,'1-0'), (-200,-250,'0-1'), (-300,300,None), (None,0,None)])
def test_agreement_limits_and_conflicting_scores(a,b,result):
    item = dict(evaluations={'0':dict(ply=9,white_cp=a),'1':dict(ply=10,white_cp=b)})
    assert agreement(item,10,20,200) == result
    assert agreement(item,11,20,200) is None  # Stale evaluations cannot adjudicate.


def test_perspective_and_invalid_scores():
    line = dict(score_type='cp',score_value=250)
    assert white_cp(line,-1) == -250
    for invalid in [None, dict(line,bound='lower'), dict(line,score_type='mate'),
                    dict(line,score_value=float('nan')), dict(line,score_value=None)]:
        assert white_cp(invalid,1) is None


def test_automatic_draw_after_50_with_ten_consecutive_plies(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--score-cp=20'])
    t=Tournament(db)
    fen=Game().initial_fen.rsplit(' ',1)[0]+' 50'
    t.create([p]*2,[Limit('nodes',1000)]*2,schedule([fen],1))
    t.resume()
    qtbot.waitUntil(lambda:t.state['index']==2,timeout=20000)
    for g in t.state['games']:
        assert len(g['moves']) == 12  # Move 50 excluded; plies 3..12 qualify.
        assert g['draw_streak']==10 and g['result']=='1/2-1/2'
        assert 'Draw by evaluation agreement' in g['termination']
        assert '±0.2 pawns' in g['termination']
        assert g['adjudication']['ply']==12
    assert db.get('tournament')['games']==t.state['games']
    t.search.close()


@pytest.mark.parametrize('result',['1-0','0-1','1/2-1/2'])
def test_manual_adjudication_paused_game_persists(qtbot,db,profile,result):
    t=Tournament(db);t.create([profile]*2,[Limit('clock',1000)]*2,schedule([Game().initial_fen],1))
    t.adjudicate(result)
    restored=Tournament(db)
    assert restored.game.outcome.result==result
    assert restored.state['games'][0]['termination']=='Manual adjudication'
    assert not restored.active and not t.clock_timer.isActive()
    restored.search.close();t.search.close()


def test_no_agreement_does_not_cancel_current_search(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--wait'])
    t=Tournament(db);t.create([p]*2,[Limit('nodes',1000)]*2,schedule([Game().initial_fen],1));t.resume()
    sid=t.search.context['id']
    with pytest.raises(ValueError,match='No evaluation agreement'):t.adjudicate()
    assert t.active and t.search.context['id']==sid
    t.pause();t.search.close()


def test_click_move_opens_final_thinking_below_first_checkpoint(qtbot,db,profile):
    db.put('profiles',[profile.__dict__]);w=Window(db);qtbot.addWidget(w)
    w.tournament.create([profile]*2,[Limit('nodes',1000)]*2,schedule([Game().initial_fen],1),3)
    w.tournament.search.completed.connect(lambda _:w.tournament.pause())
    w.resume()
    qtbot.waitUntil(lambda:w.tournament.game.cursor==1,timeout=10000)
    assert w.workspace.currentIndex()==1
    assert len(w.live_panels[0].lines)==3
    w.live_preview(0,1,1)
    assert w.live_preview_board.preview_board is not None
    w.clear_live_preview()
    w.inspect_move(1)
    assert w.workspace.currentIndex()==2 and w.view_game.cursor==0
    assert w.panels[0].record['final']
    assert len(w.panels[0].record['lines'])==3
    assert w.panels[0].record['final_result']['move']=='a2a3'
    w.close()
