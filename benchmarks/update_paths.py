"""Local comparative benchmark; timings are diagnostic, not CI thresholds."""
from time import perf_counter
from nocturne_battle.model import executable_hash
from nocturne.core.game import Game
import sys

def timed(callback, count):
    start=perf_counter()
    for _ in range(count):callback()
    return (perf_counter()-start)*1000

print(f'Executable identity, 100 calls: {timed(lambda:executable_hash(sys.executable),100):.3f} ms')
moves=['g1f3','g8f6','f3g1','f6g8']*20
# Use raw legal board pushes: repeated game adjudication stops long repetitions.
def replay():
    game=Game()
    for move in moves:game.board.push(game.board.parse_uci(move))
print(f'80-ply board replay, 100 calls: {timed(replay,100):.3f} ms')

from PySide6.QtCore import QCoreApplication
from nocturne_battle.game_browser import GameModel
from nocturne_battle.model import schedule,openings
app=QCoreApplication.instance() or QCoreApplication([])
state=dict(id='benchmark',index=0,profiles=[{'name':'A'},{'name':'B'}],games=schedule(openings(None),1000))
model=GameModel();model.update_state(state,False)
print(f'2000-game full scan, 100 calls: {timed(lambda:model.update_state(state,False),100):.3f} ms')
print(f'2000-game dirty-row update, 100 calls: {timed(lambda:model.update_state(state,False,{0}),100):.3f} ms')
