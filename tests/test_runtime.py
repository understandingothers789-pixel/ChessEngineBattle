from dataclasses import replace
import pytest
from nocturne.core.game import Game
from nocturne_battle.model import Limit, schedule
from nocturne_battle.runtime import Search, Tournament
from nocturne_battle.app import Window, ProfileDialog


@pytest.mark.parametrize('multipv',[1,2,3,4,5])
def test_real_uci_subprocess_capture(qtbot, db, profile, multipv):
    search = Search(db)
    game = Game()
    try:
        with qtbot.waitSignal(search.completed, timeout=10000) as signal:
            search.start(game,profile,Limit('nodes',9_000_000),multipv,'post-game')
        assert signal.args[0]['move'] == 'a2a3'
        records = db.records(game,profile)
        assert [r['requested'] for r in records] == [1_000_000,4_000_000,8_000_000]
        assert records[0]['actual'] == 1_100_000
        assert len(records[-1]['lines']) == multipv
        assert records[-1]['complete']
        assert records[-1]['status'] == 'completed'
        log = '\n'.join(search.engine.connection.log)
        assert '> go nodes 9000000' in log
        assert '> setoption name MultiPV value '+str(multipv) in log or multipv == 1
    finally:
        search.close()


def test_incomplete_multipv_is_not_fabricated(qtbot,db,profile):
    profile = replace(profile,arguments=profile.arguments+['--incomplete'])
    search = Search(db)
    try:
        with qtbot.waitSignal(search.completed, timeout=10000):
            search.start(Game(),profile,Limit('nodes',9_000_000),5)
        records = db.records(Game(),profile)
        assert records == []
        assert db.export()['searches'][0]['status'] == 'completed-incomplete'
    finally:
        search.close()


@pytest.mark.parametrize('limit,command',[ (Limit('depth',12),'go depth 12'), (Limit('movetime',0.2),'go movetime 200')])
def test_limit_modes_are_exclusive(qtbot,db,profile,limit,command):
    search = Search(db)
    try:
        with qtbot.waitSignal(search.completed, timeout=10000):
            search.start(Game(),profile,limit)
        commands = [line[2:] for line in search.engine.connection.log if line.startswith('> go')]
        assert commands == [command]
    finally:
        search.close()


def test_tournament_completes_pair_and_resumes(qtbot,db,profile):
    # Both first legal moves from this position force a terminal result quickly.
    fen = '7k/5Q2/6K1/8/8/8/8/8 w - - 0 1'
    tournament = Tournament(db)
    try:
        tournament.create([profile,replace(profile,name='Mock B')], [Limit('depth',1)]*2, schedule([fen],1))
        tournament.resume()
        qtbot.waitUntil(lambda: tournament.state['index'] == 2, timeout=20000)
        assert all(g['result'] != '*' for g in tournament.state['games'])
        tournament.pause()
        restored = Tournament(db)
        assert restored.state['games'] == tournament.state['games']
        restored.search.close()
    finally:
        tournament.search.close()


def test_gui_historical_comparison_previews_and_restart(qtbot,db,profile,tmp_path):
    db.put('profiles',[profile.__dict__])
    game = Game()
    search = Search(db)
    with qtbot.waitSignal(search.completed, timeout=10000):
        search.start(game,profile,Limit('nodes',9_000_000),5,'post-game')
    search.close()
    window = Window(db)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(100)
    assert len(window.panels[0].records) == 3
    assert 'Best moves agree' in window.comparison.text()
    window.panels[0].checkpoint.setCurrentIndex(0)
    window.panels[1].checkpoint.setCurrentIndex(2)
    assert window.panels[0].record['requested'] == 1_000_000
    assert window.panels[1].record['requested'] == 8_000_000
    window.preview(0,1,2)
    assert window.board.preview_board is not None
    window.end_preview(0)
    assert window.board.preview_board is None
    window.dual.setChecked(True)
    window.preview(0,1,1)
    window.preview(1,2,1)
    assert window.panels[0].board.preview_board.fen() != window.panels[1].board.preview_board.fen()
    window.panels[0].pinned = True
    window.end_preview(0)
    assert window.panels[0].board.preview_board is not None
    window.tabs.setCurrentIndex(1)
    window.graph.grab()  # Exercise graph rendering, not merely widget construction.
    window.grab().save(str(tmp_path/'studio.png'))
    window.close()


def test_registration_discovery(qtbot,profile):
    dialog = ProfileDialog(existing=profile)
    qtbot.addWidget(dialog)
    dialog.validate()
    qtbot.waitUntil(lambda: dialog.discovered is not None,timeout=10000)
    assert dialog.discovered['options']['MultiPV'].maximum == 5
    dialog.save()
    assert dialog.profile.engine_name == 'Nocturne deterministic fixture'
    dialog.close()


def test_cancel_rejects_stale_output_and_event_loop_remains_responsive(qtbot,db,profile):
    from PySide6.QtCore import QTimer
    profile = replace(profile, arguments=profile.arguments+['--wait'])
    search = Search(db)
    ticks = []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    completed = []
    search.completed.connect(completed.append)
    search.start(Game(),profile,Limit('nodes',9_000_000),5)
    qtbot.waitUntil(lambda: search.engine.connection.phase == 'search',timeout=10000)
    search.cancel()
    qtbot.wait(300)
    assert len(ticks) > 5
    assert completed == []
    assert db.export()['searches'][0]['status'] == 'interrupted'
    assert db.records(Game(),profile) == []
    timer.stop()
    search.close()


def test_pause_and_resume_mid_match(qtbot,db,profile):
    profile = replace(profile,arguments=profile.arguments+['--wait'])
    tournament = Tournament(db)
    fen = '7k/5Q2/6K1/8/8/8/8/8 w - - 0 1'
    tournament.create([profile,profile],[Limit('nodes',9_000_000)]*2,schedule([fen],1))
    tournament.resume()
    qtbot.waitUntil(lambda: len(tournament.state['games'][0]['moves']) > 0,timeout=10000)
    tournament.pause()
    saved = db.get('tournament')
    tournament.search.close()
    restored = Tournament(db)
    assert restored.game.cursor == len(saved['games'][saved['index']]['moves'])
    restored.resume()
    qtbot.waitUntil(lambda: restored.state['index'] == 2,timeout=20000)
    assert all(g['result'] != '*' for g in restored.state['games'])
    restored.search.close()


def test_export_actual_json_csv_and_pgn(qtbot,db,profile,tmp_path,monkeypatch):
    import json
    import chess.pgn
    import io
    from nocturne_battle import app
    db.put('profiles',[profile.__dict__])
    window = Window(db)
    qtbot.addWidget(window)
    state = schedule([Game().initial_fen],1)
    state[0]['moves'] = ['e2e4','e7e5']
    window.tournament.create([profile,profile],[Limit()]*2,state)
    search = Search(db)
    with qtbot.waitSignal(search.completed,timeout=10000):
        search.start(Game(),profile,Limit('nodes',9_000_000),5,'post-game')
    search.close()
    for suffix in ['json','csv','pgn']:
        destination = tmp_path/('match.'+suffix)
        monkeypatch.setattr(app.QFileDialog,'getSaveFileName',lambda *args, d=destination, **kwargs: (str(d),''))
        window.export()
        text = destination.read_text()
        if suffix == 'json':
            assert len(json.loads(text)['snapshots']) == 3
        elif suffix == 'csv':
            assert len(text.splitlines()) == 16
            assert 'post-game' in text
        else:
            game = chess.pgn.read_game(io.StringIO(text))
            assert [m.uci() for m in game.mainline_moves()] == ['e2e4','e7e5']
            assert 'BattleConfig' in game.headers
    window.close()
