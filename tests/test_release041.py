from nocturne_battle.app import Window
from nocturne_battle.model import Database, Limit, schedule, openings
from PySide6.QtWidgets import QAbstractItemView


def test_score_color_swaps_and_resizable_table(qtbot,db,profile):
    w=Window(db);qtbot.addWidget(w);w.show()
    games=schedule(openings(None),2)
    w.tournament.create([profile]*2,[Limit()]*2,games)
    for game,result in zip(w.tournament.state['games'],['1-0','0-1','1/2-1/2','1-0']):game['result']=result
    w.tournament.save()
    assert 'A 2.5' in w.score_label.text() and '1.5 B' in w.score_label.text()
    qtbot.wait(30)
    w.games_table.fit_columns()
    assert w.games_table.columnWidth(1)<=60
    assert w.games_table.horizontalScrollMode()==QAbstractItemView.ScrollMode.ScrollPerPixel
    w.games_table.setColumnWidth(2,189)
    w.save_settings();path=db.path;w.close()
    restored=Window(Database(path));qtbot.addWidget(restored);restored.show();qtbot.wait(50)
    assert restored.games_table.columnWidth(2)==189
    assert len(restored.board_splitter.sizes())==2
    restored.close()
