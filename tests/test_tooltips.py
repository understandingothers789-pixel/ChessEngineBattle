from PySide6.QtWidgets import QPushButton,QComboBox,QLineEdit,QSpinBox,QCheckBox
from nocturne_battle.app import Window
from nocturne_battle.widgets import ProfileDialog


def test_window_interactive_controls_have_help(qtbot,db):
    window=Window(db);qtbot.addWidget(window)
    kinds=(QPushButton,QComboBox,QLineEdit,QSpinBox,QCheckBox)
    controls=[w for w in window.findChildren(QPushButton)]+[w for w in window.findChildren(QComboBox)]+[w for w in window.findChildren(QLineEdit)]+[w for w in window.findChildren(QSpinBox)]+[w for w in window.findChildren(QCheckBox)]
    assert controls and all(w.toolTip() for w in controls)
    assert window.board.toolTip()
    window.close()


def test_discovered_engine_options_have_help(qtbot,profile):
    dialog=ProfileDialog(existing=profile);qtbot.addWidget(dialog)
    dialog.validate()
    qtbot.waitUntil(lambda:dialog.discovered is not None,timeout=10000)
    assert all(w.toolTip() for w in dialog.option_widgets.values())
    dialog.close()


def test_search_budget_tooltips_follow_each_engine_mode(qtbot, db):
    window = Window(db)
    qtbot.addWidget(window)
    assert window.mode.currentText() == 'clock'
    assert window.mode_b.currentText() == 'Same as A'
    assert 'base time' in window.mode.toolTip()
    assert 'Same as A' in window.mode_b.toolTip()
    window.mode.setCurrentText('movetime')
    window.mode_b.setCurrentText('depth')
    assert 'seconds' in window.budgets[0].toolTip()
    assert 'depth 12' in window.budgets[1].toolTip()
    assert 'enter 12' in window.limit_form.labelForField(window.budgets[1]).toolTip()
    window.mode_b.setCurrentText('Same as A')
    assert 'seconds' in window.budgets[1].toolTip()
    window.mode.setCurrentText('nodes')
    assert 'nodes' in window.budgets[0].toolTip()
    assert 'nodes' in window.budgets[1].toolTip()
    window.close()
