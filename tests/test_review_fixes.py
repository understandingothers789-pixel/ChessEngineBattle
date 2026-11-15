from nocturne_battle.clocks import MatchClock
from nocturne_battle.model import Limit, schedule, openings
from nocturne_battle.app import Window


def test_buffer_deadline_matches_move_receipt_and_preserves_actual_elapsed():
    clock=MatchClock.create([Limit('clock',1000,100)]*2,True)
    clock.start(1,now=0,wall_now=0)
    assert not clock.expired(200_000_000,now=1_100_000_000)
    assert clock.expired(200_000_000,now=1_200_000_000)
    flag,elapsed=clock.stop(now=1_100_000_000,add_increment=True,buffer_ns=200_000_000)
    assert flag is None and elapsed == 1_100_000_000
    assert clock.remaining[1] == 200_000_000


def test_review_clocks_use_both_sides_and_refresh_without_live_tick(qtbot,db,profile):
    w=Window(db);qtbot.addWidget(w)
    w.tournament.create([profile]*2,[Limit('clock',10000)]*2,schedule(openings(None),1))
    item=w.tournament.state['games'][0]
    item['move_searches']={'1': {'clock_after': {'remaining_ns': {'1': 8_000_000_000,'-1':10_000_000_000}}}}
    w.follow_live=False
    w.view_game.cursor=1
    w.update_clocks()
    assert w.scoreboard.clocks[0].text()=='00:08.0'
    assert w.scoreboard.clocks[1].text()=='00:10.0'
    w.tournament.pause()
    assert w.pause_status.text()=='PAUSED'
    w.tournament.search.close()


def test_divergence_is_cleared_when_selected_lines_stop_differing():
    from types import SimpleNamespace
    from nocturne.core.game import Game
    class Panel:
        divergence_index=None
        def __init__(self,pv): self.lines={1: {'pv':pv}}
        def set_full(self,full): pass
    panels=[Panel(['e2e4','e7e5']),Panel(['e2e4','c7c5'])]
    view=SimpleNamespace(live_panels=panels, live_games=[Game(),Game()],
                         full_variations=SimpleNamespace(isChecked=lambda:True))
    Window.mark_main_divergence(view)
    assert [p.divergence_index for p in panels]==[1,1]
    panels[1].lines={1: {'pv':['e2e4','e7e5']}}
    Window.mark_main_divergence(view)
    assert all(p.divergence_index is None for p in panels)
