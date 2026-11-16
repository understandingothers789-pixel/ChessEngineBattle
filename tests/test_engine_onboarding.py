import json
from dataclasses import replace
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


def test_edit_refreshes_names_and_preserves_unloaded_side(qtbot, db, profile, monkeypatch):
    from nocturne_battle import app
    w = Window(db); qtbot.addWidget(w)
    w.profiles = [profile, replace(profile, name='Second', id='second')]
    w.populate_profiles()
    w.engines[0].setCurrentIndex(0); w.engines[1].setCurrentIndex(-1)
    def accept(dialog):
        dialog.profile = replace(profile, name='Renamed')
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(app.ProfileDialog, 'exec', accept)
    w.edit_engine_settings(0)
    assert [w.engines[0].itemText(i) for i in range(w.engines[0].count())] == ['Renamed', 'Second']
    assert w.engines[1].currentIndex() == -1
    assert db.get('profiles')[0]['name'] == 'Renamed'
    assert db.get('workspace')['engines'] == [0, -1]
    w.close()


def test_shared_profile_edit_adds_selectable_copy(qtbot, db, profile, monkeypatch):
    from nocturne_battle import app
    w = Window(db); qtbot.addWidget(w)
    w.profiles = [profile]; w.populate_profiles()
    w.engines[0].setCurrentIndex(0); w.engines[1].setCurrentIndex(0)
    def accept(dialog):
        dialog.profile = replace(profile, name='New engine', id='new-profile')
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(app.ProfileDialog, 'exec', accept)
    w.edit_engine_settings(0)
    assert [w.engines[0].itemText(i) for i in range(w.engines[0].count())] == ['Mock A', 'New engine · A']
    assert w.engines[0].currentIndex() == 1 and w.engines[1].currentIndex() == 0
    assert len(db.get('profiles')) == 2
    w.close()


def test_selecting_different_executable_keeps_original_profile(qtbot, db, profile, monkeypatch, tmp_path):
    from nocturne_battle import app
    w = Window(db); qtbot.addWidget(w)
    w.profiles = [profile, replace(profile, name='Other', id='other')]; w.populate_profiles()
    w.engines[0].setCurrentIndex(0); w.engines[1].setCurrentIndex(1)
    def accept(dialog):
        dialog.profile = replace(profile, name='New engine', path=str(tmp_path/'new-engine'), id='new-profile')
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(app.ProfileDialog, 'exec', accept)
    w.edit_engine_settings(0)
    assert [p.name for p in w.profiles] == ['Mock A', 'Other', 'New engine']
    assert w.engines[0].currentIndex() == 2 and w.engines[1].currentIndex() == 1
    assert db.get('workspace')['engines'] == [2, 1]
    w.close()
