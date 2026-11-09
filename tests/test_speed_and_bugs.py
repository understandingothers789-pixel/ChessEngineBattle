from pathlib import Path
from nocturne_battle.model import executable_hash,_hash_unchanged_file,schedule,openings,Limit
from nocturne_battle.app import Window
from nocturne_battle.runtime import Tournament
from nocturne_battle.experiments import ExperimentRunner,build_experiment


def test_hash_cache_hits_and_file_changes_invalidate(tmp_path):
    file=tmp_path/'engine';file.write_bytes(b'first')
    _hash_unchanged_file.cache_clear()
    original=executable_hash(file)
    assert executable_hash(file)==original
    assert _hash_unchanged_file.cache_info().hits==1
    file.write_bytes(b'updated binary')
    assert executable_hash(file)!=original
    file.unlink()
    import pytest
    with pytest.raises(FileNotFoundError):executable_hash(file)


def test_viewer_appends_new_moves_without_replaying_old_ones(qtbot,db,profile,monkeypatch):
    from nocturne.core.game import Game
    db.put('profiles',[profile.__dict__]);w=Window(db);qtbot.addWidget(w)
    games=schedule(openings(None),1);games[0]['id']='first';games[0]['moves']=['e2e4']
    w.tournament.create([profile]*2,[Limit()]*2,games)
    original=w.view_game
    calls=[];play=Game.play
    def observed(self,move,*args,**kwargs):
        if self is original:calls.append(move.uci())
        return play(self,move,*args,**kwargs)
    monkeypatch.setattr(Game,'play',observed)
    games[0]['moves'].append('e7e5');w.load_game(0)
    assert w.view_game is original
    assert calls==['e7e5']
    assert w.view_game.board.fen()!=w.tournament.game.board.fen() # Independent view.
    w.close()


def test_clicked_game_and_pin_state_stay_consistent(qtbot,db,profile):
    db.put('profiles',[profile.__dict__]);w=Window(db);qtbot.addWidget(w)
    w.tournament.create([profile]*2,[Limit()]*2,schedule(openings(None),2))
    w.select_game(2)
    assert w.game_selector.currentIndex()==2
    w.panels[0].pin_control.setChecked(True)
    assert w.panels[0].pinned
    w.show_game()
    assert not w.panels[0].pin_control.isChecked() and not w.panels[0].pinned
    w.close()


def test_experiment_cannot_replace_unrelated_new_match(db,profile):
    t=Tournament(db);runner=ExperimentRunner(db,t)
    runner.create(build_experiment(profile,1000,[2],openings(None),1))
    runner.active=True
    t.create([profile]*2,[Limit()]*2,schedule(openings(None),1))
    unrelated=t.state['id']
    assert not runner.active
    runner.next()
    assert t.state['id']==unrelated
    t.search.close()
