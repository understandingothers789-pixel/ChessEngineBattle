from nocturne_battle.app import Window
from nocturne_battle.model import Limit,schedule,openings
from nocturne_battle.theme import stylesheet


def test_studio_onboarding_navigation_and_scorecards(qtbot,db,profile,qapp):
    original=qapp.styleSheet();qapp.setStyleSheet(stylesheet())
    w=Window(db);qtbot.addWidget(w);w.show()
    try:
        w.resize(1280,800);qtbot.wait(30)
        assert w.width()==1280 and w.height()==800
        assert w.onboarding.isVisible()
        assert w.setup_button.isVisible() and w.library_button.isVisible()
        assert all(not card.isVisible() for card in w.live_analysis_cards)
        games=schedule(openings(None),1)
        w.tournament.create([profile]*2,[Limit('clock',10000)]*2,games,3)
        w.tournament.state['games'][0]['result']='1-0'
        w.tournament.state['games'][1]['result']='1/2-1/2'
        w.tournament.save()
        assert not w.onboarding.isVisible()
        assert w.scoreboard.points[0].text()=='1.5' and w.scoreboard.points[1].text()=='0.5'
        assert w.scoreboard.progress.value()==2
        assert w.result_cards.values[0].text()=='1.5 : 0.5'
        assert w.scoreboard.clocks[0].text().startswith('00:10')
        w.nav_buttons[3].click();assert w.workspace.currentIndex()==3
        w.nav_buttons[1].click();assert w.live_area.isVisible()
        w.open_setup();assert w.setup_dialog.isVisible()
        w.setup_dialog.hide();w.reset_view()
        assert w.game_selector.isVisible()
        w.resize(1920,1080);qtbot.wait(30)
        assert w.width()==1920 and w.height()==1080
    finally:
        w.close();qapp.setStyleSheet(original)
