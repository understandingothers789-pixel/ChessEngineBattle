from dataclasses import replace
from nocturne_battle.app import Window
from nocturne_battle.model import Database, Limit, schedule, openings


def test_saved_depth_variations_survive_restart_and_hover(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--depth-evolution'])
    db.put('profiles',[p.__dict__]);w=Window(db);qtbot.addWidget(w);w.show()
    w.tournament.create([p]*2,[Limit('nodes',9_000_000)]*2,schedule(openings(None),1),3)
    w.tournament.search.completed.connect(lambda _:w.tournament.pause())
    w.resume();qtbot.waitUntil(lambda:w.tournament.game.cursor==1,timeout=10000)
    w.inspect_move(1)
    assert w.view_game.cursor==1
    assert [r['depth'] for r in w.saved_records[0][1:5]]==[4,8,10,12]
    w.saved_selectors[0].setCurrentIndex(1)
    assert all(line['depth']==4 for line in w.live_panels[0].lines.values())
    fen=w.view_game.board.fen();w.live_preview(0,2,2)
    assert w.live_preview_board.preview_board is not None
    assert w.view_game.board.fen()==fen
    path=db.path;w.close()
    restored=Window(Database(path));qtbot.addWidget(restored);restored.show()
    restored.inspect_move(1)
    assert len(restored.live_panels[0].lines)==3
    assert restored.saved_selectors[0].count()>=5
    assert restored.live_area.isVisible()
    restored.close()


def test_setup_never_hides_analysis_and_pause_is_always_accessible(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--wait'])
    db.put('profiles',[p.__dict__]);w=Window(db);qtbot.addWidget(w);w.show()
    w.tournament.create([p]*2,[Limit('nodes',1000)]*2,schedule(openings(None),1),3)
    w.resume();w.workspace.setCurrentIndex(0)
    assert w.setup_dialog.isVisible() and w.live_area.isVisible()
    w.setup_dialog.hide()
    assert w.pause_button.isVisible()
    w.pause_button.click();assert not w.tournament.active
    assert w.pause_button.text()=='Resume'
    w.pause_button.click();assert w.tournament.active
    w.close()


def test_review_is_not_overwritten_by_live_search_and_return_restores(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--wait'])
    db.put('profiles',[p.__dict__]);w=Window(db);qtbot.addWidget(w);w.show()
    w.tournament.create([p]*2,[Limit('nodes',1000)]*2,schedule(openings(None),1),3)
    w.resume();qtbot.waitUntil(lambda:w.tournament.game.cursor>=2,timeout=10000)
    w.inspect_move(1)
    lines=dict(w.live_panels[0].lines)
    qtbot.waitUntil(lambda:w.tournament.game.cursor>=3,timeout=10000)
    assert w.live_panels[0].lines==lines and w.view_game.cursor==1
    w.return_live()
    assert w.follow_live and w.view_game.cursor==w.tournament.game.cursor
    assert 'Live analysis' in w.analysis_heading.text()
    w.close()
