import json
from pathlib import Path
import pytest
from PySide6.QtWidgets import QDialog
from nocturne_battle.app import Window
from nocturne_battle.widgets import ProfileDialog


def test_engine_picker_opens_directly_and_cancel_is_safe(qtbot,db,monkeypatch):
    from nocturne_battle import app
    w=Window(db);qtbot.addWidget(w)
    calls=[]
    def browse(*args,**kwargs):calls.append(args);return '', ''
    monkeypatch.setattr(app.QFileDialog,'getOpenFileName',browse)
    w.load_a_button.click()
    assert len(calls)==1
    assert 'engine executable' in calls[0][1]
    assert w.profiles==[]
    assert w.tournament.search.context is None
    w.close()


def test_selected_file_is_prepopulated_without_execution(qtbot,profile):
    dialog=ProfileDialog(selected_path=profile.path);qtbot.addWidget(dialog)
    assert dialog.path.text()==profile.path
    assert dialog.name.text()==Path(profile.path).stem
    assert dialog.connection.phase=='closed'
    # Intentional Test engine click starts the protocol check.
    dialog.args.setText(json.dumps(profile.arguments))
    dialog.test_button.click()
    qtbot.waitUntil(lambda:dialog.discovered is not None,timeout=10000)
    assert 'Click Save engine' in dialog.status.text()
    dialog.save()
    assert dialog.profile.identity==profile.identity
    dialog.close()


def test_load_assigns_engine_and_unload_does_not_select_last_profile(qtbot,db,profile,monkeypatch):
    from nocturne_battle import app
    w=Window(db);qtbot.addWidget(w)
    monkeypatch.setattr(app.QFileDialog,'getOpenFileName',lambda *a,**k:(profile.path,''))
    def accept(dialog):
        assert dialog.path.text()==profile.path
        dialog.profile=profile
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(app.ProfileDialog,'exec',accept)
    w.load_b_button.click()
    assert w.selected_profiles()==[profile,profile]
    assert db.get('profiles')[0]['identity']==profile.identity
    w.unload_engine(1)
    assert w.engines[1].currentIndex()==-1
    with pytest.raises(ValueError,match='both A and B'):w.selected_profiles()
    assert db.get('profiles')  # Removing the selection retains the saved engine.
    assert db.get('workspace')['engines'][1]==-1
    w.close()
