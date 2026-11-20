import csv
from nocturne_battle.review_tools import capture_conditions, apply_conditions, export_move_statistics
from nocturne_battle.app import Window


def test_match_preset_restores_conditions_without_changing_engines(qtbot,db,profile):
    db.put('profiles',[profile.__dict__])
    w=Window(db);qtbot.addWidget(w)
    w.mode.setCurrentText('clock');w.clock_bases[0].setValue(3)
    w.clock_buffer.setValue(0.35);w.draw_start.setValue(42);w.pairs.setValue(7)
    w.play_pv.setValue(1);w.play_pv_b.setValue(2)
    saved=capture_conditions(w);engines=[c.currentIndex() for c in w.engines]
    w.clock_bases[0].setValue(1);w.draw_start.setValue(30);w.pairs.setValue(1)
    w.play_pv.setValue(4);w.play_pv_b.setValue(5)
    apply_conditions(w,saved)
    assert (w.play_pv.value(), w.play_pv_b.value()) == (1, 2)
    saved["values"].pop("play_pv_b")
    apply_conditions(w,saved)
    assert w.play_pv_b.value() == 1
    assert w.clock_bases[0].value()==3 and w.draw_start.value()==42 and w.pairs.value()==7
    assert w.clock_buffer.value()==0.35
    assert [c.currentIndex() for c in w.engines]==engines


def test_export_statistics_uses_white_perspective_and_actual_elapsed(tmp_path):
    class DB:
        def search_run(self,key):
            return {'fen':'8/8/8/8/8/8/8/8 b - - 0 32','final_result':{'lines':{'1':{'score_type':'cp','score_value':70,'nodes':12345,'depth':20,'time':900,'tbhits':3}}}}
    item={'a_white':True,'move_searches':{'10':{'search_run_id':'x','played_move':'a7a6','elapsed_ns':1_000_000_000,'clock_after':{'remaining_ns':{'-1':2_000_000_000}}}}}
    path=tmp_path/'stats.csv';export_move_statistics(item,DB(),path)
    with path.open(encoding='utf-8-sig') as stream: rows=list(csv.DictReader(stream))
    assert rows[0]['eval_white_pawns']=='-0.7'
    assert rows[0]['engine_side']=='B' and rows[0]['nodes']=='12345'
    assert rows[0]['elapsed_seconds']=='1.0' and rows[0]['clock_after_seconds']=='2.0'
