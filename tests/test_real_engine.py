"""Opt-in real UCI compatibility. Never downloads or bundles an engine."""
import os
import pytest
import chess.pgn
import io
from nocturne.core.game import Game
from nocturne_battle.model import Profile,Limit,executable_hash,schedule,openings
from nocturne_battle.runtime import Search,Tournament

engine_path=os.environ.get('NOCTURNE_UCI_ENGINE')
pytestmark=pytest.mark.skipif(not engine_path,reason='Set NOCTURNE_UCI_ENGINE to an explicit user-provided UCI executable')


def test_real_engine_compatibility(qtbot,db):
    from nocturne.gui.uci_connection import UciConnection
    connection=UciConnection()
    with qtbot.waitSignal(connection.discovered,timeout=30000) as result:connection.launch(engine_path)
    data=result.args[0];connection.close()
    assert data['name'] and data['options']
    profile=Profile(data['name'],engine_path,{},identity=executable_hash(engine_path),engine_name=data['name'])
    search=Search(db)
    try:
        for limit in [Limit('nodes',1200000),Limit('depth',8),Limit('movetime',0.2)]:
            with qtbot.waitSignal(search.completed,timeout=60000) as final:search.start(Game(),profile,limit)
            assert Game().board.parse_uci(final.args[0]['move'])
        for pv in range(1,6):
            if pv>1 and 'MultiPV' not in data['options']:break
            with qtbot.waitSignal(search.completed,timeout=60000):search.start(Game(),profile,Limit('nodes',1200000),pv,kind='independent')
            assert search.last_completed['status']=='completed'
        search.start(Game(),profile,Limit('nodes',1000000000));qtbot.wait(100);search.cancel()
        assert search.context is None
    finally:search.close()
    tournament=Tournament(db)
    tournament.create([profile]*2,[Limit('nodes',10000)]*2,schedule(openings(None),1))
    tournament.state['max_plies']=4
    tournament.resume()
    qtbot.waitUntil(lambda:tournament.state['index']==2,timeout=120000)
    for item in tournament.state['games']:
        game=Game(item['fen'])
        for move in item['moves']:game.play(game.board.parse_uci(move))
        assert not chess.pgn.read_game(io.StringIO(game.pgn())).errors
    tournament.search.close()
