from dataclasses import replace
from nocturne_battle.app import Window
from nocturne_battle.model import Limit,schedule,openings
from nocturne_battle.statistics import dashboard
from nocturne_battle.tablebases import TablebaseDialog


def test_pair_results_exclude_unfinished_pairs():
    games=schedule(openings(None),3)
    for g,r in zip(games,['1-0','1/2-1/2','0-1','1-0','1-0','*']):g['result']=r
    result=dashboard(dict(games=games))
    assert (result['pair_wins'],result['pair_losses'],result['pair_draws'])==(1,1,0)
    assert result['wins']==2 and result['losses']==2 and result['draws']==1
    assert result['elo']==0


def test_reset_keeps_match_running_and_game_picker_accessible(qtbot,db,profile):
    p=replace(profile,arguments=profile.arguments+['--silent'])
    db.put('profiles',[p.__dict__]);w=Window(db);qtbot.addWidget(w);w.show()
    w.tournament.create([p]*2,[Limit()]*2,schedule(openings(None),2),3)
    w.resume();sid=w.tournament.search.context['id']
    assert w.game_selector.isVisible() and w.game_selector.count()==4
    w.game_selector.setCurrentIndex(1);assert not w.follow_live
    w.full_variations.setChecked(True);w.reset_view()
    assert w.follow_live and not w.full_variations.isChecked()
    assert w.tournament.active and w.tournament.search.context['id']==sid
    assert w.game_selector.currentIndex()==0
    w.close()


def test_shared_syzygy_checks_support_and_preserves_original_profiles(qtbot,profile,tmp_path):
    (tmp_path/'KQvK.rtbw').write_bytes(b'test-only')
    a=replace(profile,arguments=profile.arguments+['--syzygy'])
    b=replace(profile,name='Unsupported')
    dialog=TablebaseDialog([a,b]);qtbot.addWidget(dialog)
    dialog.path.setText(str(tmp_path));dialog.begin()
    qtbot.waitUntil(lambda:dialog.result()==dialog.DialogCode.Accepted,timeout=15000)
    assert dialog.profiles[0].options['SyzygyPath']==str(tmp_path)
    assert dialog.profiles[0].options['SyzygyProbeLimit']==5
    assert 'SyzygyPath' not in a.options and 'SyzygyPath' not in dialog.profiles[1].options
    assert 'unsupported' in dialog.messages[1]


def test_shared_syzygy_keeps_existing_paths(qtbot,profile,tmp_path):
    (tmp_path/'KQvK.rtbw').write_bytes(b'test-only')
    p=replace(profile,options=dict(profile.options,SyzygyPath='existing'))
    dialog=TablebaseDialog([p,p]);qtbot.addWidget(dialog)
    dialog.path.setText(str(tmp_path));dialog.begin()
    assert dialog.result()==dialog.DialogCode.Accepted
    assert all(p.options['SyzygyPath']=='existing' for p in dialog.profiles)
