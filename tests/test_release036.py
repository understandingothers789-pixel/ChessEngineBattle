from pathlib import Path
from nocturne_battle.time_editor import MinutesSeconds
from nocturne_battle.model import openings
from nocturne_battle.widgets import ProfileDialog
from nocturne.engine.uci_types import UciOption


def test_seconds_editor_preserves_legacy_minute_settings(qtbot):
    w=MinutesSeconds();qtbot.addWidget(w)
    assert w.minutes.value()==0 and w.seconds.value()==10
    w.setValue(1.5)
    assert w.minutes.value()==1 and w.seconds.value()==30
    assert w.value()==1.5


def test_engine_defaults_and_units(qtbot):
    w=ProfileDialog();qtbot.addWidget(w)
    w.discover(dict(name='Fixture',options={
        'Threads':UciOption('Threads','spin','1',1,16),
        'Hash':UciOption('Hash','spin','16',1,4096),
        'Skill Level':UciOption('Skill Level','spin','10',0,20),
        'UCI_LimitStrength':UciOption('UCI_LimitStrength','check','true')}))
    assert w.option_widgets['Threads'].value()==2
    assert w.option_widgets['Hash'].value()==1024
    assert 'MB' in w.option_widgets['Hash'].suffix()
    assert w.option_widgets['Skill Level'].value()==20
    assert not w.option_widgets['UCI_LimitStrength'].isChecked()
    w.close()


def test_included_suites_are_valid():
    root=Path(__file__).parents[1]/'src/nocturne_battle/books'
    counts={p.name:len(openings(p)) for p in root.glob('*.epd')}
    assert counts=={'Drawkiller_balanced_big.epd':15962,'4mvs_+90_+99.epd':635,'6mvs_+90_+99.epd':2933}
