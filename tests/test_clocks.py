import json
from dataclasses import replace
import pytest
from nocturne_battle.clocks import MatchClock
from nocturne_battle.model import Limit,schedule,openings
from nocturne_battle.runtime import Tournament
from nocturne_battle.app import Window


def test_integer_clock_accounting_pause_increment_and_recovery():
    c=MatchClock.create([Limit('clock',1000,100),Limit('clock',2000,500)],True)
    assert c.uci()=='go wtime 1000 btime 2000 winc 100 binc 500'
    c.start(1,now=0,wall_now=0)
    assert c.left(1,now=250_000_000)==750_000_000
    flag,elapsed=c.stop(now=250_000_000,add_increment=True)
    assert flag is None and elapsed==250_000_000
    assert c.remaining[1]==850_000_000
    c.start(-1,now=0,wall_now=0)
    frozen=c.payload()
    restored=MatchClock.restore(frozen,wall_now=300_000_000)
    assert restored.active is None and restored.remaining[-1]==1_700_000_000
    c.stop(now=300_000_000)
    assert c.remaining[-1]==1_700_000_000 # Pause earns no increment.


def test_expiration_never_awards_increment():
    c=MatchClock.create([Limit('clock',1,100)]*2,True)
    c.start(1,now=0,wall_now=0)
    flag,_=c.stop(now=1_000_000,add_increment=True)
    assert flag==1 and c.remaining[1]==0
    assert MatchClock.create([Limit('clock',1000,20),Limit('clock',3000,50)],False).uci()=='go wtime 3000 btime 1000 winc 50 binc 20'


@pytest.mark.parametrize('limit',[Limit('clock',0),Limit('clock',1,-1),Limit('clock',1.5,0),Limit('clock',2**31,0)])
def test_invalid_clock_limits(limit):
    with pytest.raises(ValueError):limit.validate()


def test_uci_clock_commands_and_paired_reset(qtbot,db,profile):
    t=Tournament(db)
    t.create([profile]*2,[Limit('clock',1000,50),Limit('clock',2000,100)],schedule(openings(None),1))
    t.state['max_plies']=2
    t.resume()
    qtbot.waitUntil(lambda:t.state['index']==2,timeout=15000)
    commands=[line[2:] for line in t.search.engine.connection.log if line.startswith('> go')]
    assert commands[0]=='go wtime 1000 btime 2000 winc 50 binc 100'
    assert commands[2]=='go wtime 2000 btime 1000 winc 100 binc 50'
    assert all('nodes' not in c and 'depth' not in c and 'movetime' not in c for c in commands)
    link=t.state['games'][0]['move_searches']['1']
    assert link['elapsed_ns']>=0
    assert link['clock_after']['remaining_ns'][1] == link['clock_before']['remaining_ns'][1]-link['elapsed_ns']+50_000_000
    searches=db.export()['searches']
    assert all('wtime' in r['clock_go'] for r in searches)
    assert all(g['result']=='1/2-1/2' for g in t.state['games'])
    assert t.clock is None
    t.search.close()


def test_time_forfeit_stops_search_and_records_no_late_move(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--wait'])
    t=Tournament(db);t.create([p]*2,[Limit('clock',20,1000)]*2,schedule(openings(None),1))
    t.resume()
    qtbot.waitUntil(lambda:t.state['index']==2,timeout=15000)
    assert all(g['result']=='0-1' and g['moves']==[] and g['termination']=='Time forfeit' for g in t.state['games'])
    assert all(r['status']=='time-forfeit' for r in db.export()['searches'])
    t.search.close()


def test_pause_freezes_remaining_time_and_resume_starts_new_search(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--wait'])
    t=Tournament(db);t.create([p]*2,[Limit('clock',1000,0)]*2,schedule(openings(None),1))
    t.resume()
    qtbot.waitUntil(lambda:t.clock.active is not None,timeout=10000)
    old=t.search.context['id'];qtbot.wait(30);t.pause()
    frozen=t.clock.remaining[1]
    qtbot.wait(100)
    assert t.clock.remaining[1]==frozen and t.clock.active is None
    assert 0<frozen<1_000_000_000
    saved=db.get('tournament')['games'][0]['clock']
    assert saved['active'] is None
    t.resume()
    assert t.search.context['id']!=old
    t.pause();t.search.close()


def test_timeout_draw_when_opponent_has_only_king(db,profile):
    fen='7k/8/6K1/8/8/8/8/R7 w - - 0 1'
    t=Tournament(db);t.create([profile]*2,[Limit('clock',1000)]*2,schedule([fen],1))
    t.forfeit(1)
    assert t.state['games'][0]['result']=='1/2-1/2'
    t.search.close()


def test_gui_clock_fields_and_opening_pair_explanation(qtbot,db,profile):
    db.put('profiles',[profile.__dict__]);w=Window(db);qtbot.addWidget(w)
    w.mode.setCurrentText('clock');w.clock_bases[0].setValue(1);w.clock_increments[0].setValue(0.5)
    assert w.limits()[0]==Limit('clock',60000,500)
    assert not w.budgets[0].isEnabled()
    w.pairs.setValue(12)
    assert '24 games' in w.pair_description.text()
    w.save_settings()
    assert db.get('workspace')['clock_bases'][0]==1
    w.close()


def test_unclean_restart_charges_saved_running_clock(db,profile):
    import time
    t=Tournament(db);t.create([profile]*2,[Limit('clock',1000)]*2,schedule(openings(None),1))
    t.clock.start(1,now=0,wall_now=time.time_ns()-50_000_000)
    t.save()
    restored=Tournament(db)
    assert restored.clock.active is None
    assert 0<restored.clock.remaining[1]<=950_000_000
    assert restored.clock.remaining[-1]==1_000_000_000
    t.clock.stop(now=0);t.search.close();restored.search.close()


def test_asymmetric_clock_export_uses_color_specific_headers(qtbot,db,profile,tmp_path,monkeypatch):
    import io,chess.pgn
    from nocturne_battle import app
    db.put('profiles',[profile.__dict__]);w=Window(db);qtbot.addWidget(w)
    w.tournament.create([profile]*2,[Limit('clock',60000,1000),Limit('clock',120000,2000)],schedule(openings(None),1))
    path=tmp_path/'clocks.pgn'
    monkeypatch.setattr(app.QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    w.export();stream=io.StringIO(path.read_text())
    first=chess.pgn.read_game(stream);second=chess.pgn.read_game(stream)
    assert first.headers['TimeControl']=='?'
    assert first.headers['WhiteTimeControl']=='60+1' and first.headers['BlackTimeControl']=='120+2'
    assert second.headers['WhiteTimeControl']=='120+2' and second.headers['BlackTimeControl']=='60+1'
    w.close()


def test_whole_suite_button_sets_two_games_per_book_entry(qtbot,db,profile,tmp_path):
    db.put('profiles',[profile.__dict__]);w=Window(db);qtbot.addWidget(w)
    book=tmp_path/'openings.pgn'
    book.write_text('[Event "One"]\n\n1. e4 *\n\n[Event "Two"]\n\n1. d4 *\n')
    w.book.setText(str(book));w.use_full_opening_suite()
    assert w.pairs.value()==2
    assert '4 games' in w.pair_description.text()
    w.close()
