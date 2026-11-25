"""Explicit review actions and reusable match conditions."""
import csv
from .adjudication import DEFAULT_RULE
from .model import Limit, Profile, executable_hash
from .runtime import playing_multipv
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QInputDialog,QMessageBox
from .adjudication import white_cp


def export_move_statistics(item, db, path):
    with open(path,'w',newline='',encoding='utf-8-sig') as stream:
        out=csv.writer(stream)
        out.writerow(['ply','move_number','color','engine_side','played_move_uci','eval_white_pawns','mate_score','depth','nodes','engine_time_ms','elapsed_seconds','clock_after_seconds','tb_hits'])
        for key,link in sorted(item.get('move_searches',{}).items(),key=lambda pair:int(pair[0])):
            run=db.search_run(link['search_run_id'])
            if not run: continue
            fen=run['fen'].split();turn=1 if fen[1]=='w' else -1
            lines=run.get('final_result',{}).get('lines',{})
            line=lines.get('1',lines.get(1,{}));cp=white_cp(line,turn)
            remaining=link.get('clock_after',{}).get('remaining_ns',{})
            clock=remaining.get(str(turn),remaining.get(turn))
            elapsed=link.get('elapsed_ns')
            out.writerow([key,fen[5],'White' if turn==1 else 'Black','A' if (turn==1)==item['a_white'] else 'B',link.get('played_move',link.get('bestmove','')),cp/100 if cp is not None else '',line.get('score_value','')*turn if line.get('score_type')=='mate' else '',line.get('depth',''),line.get('nodes',''),line.get('time',''),elapsed/1e9 if elapsed is not None else '',clock/1e9 if clock is not None else '',line.get('tbhits','')])


VALUE_FIELDS=('pairs','play_pv','play_pv_b','draw_start','clock_buffer','silence_timeout','seed','sprt_h0','sprt_h1','sprt_alpha','sprt_beta')
TEXT_FIELDS=('book','checkpoint','maximum')
CHECK_FIELDS=('auto_draw','keep_best_changes','randomized','sprt_enabled')


def capture_conditions(window):
    return dict(values={name:getattr(window,name).value() for name in VALUE_FIELDS},
                texts={name:getattr(window,name).text() for name in TEXT_FIELDS},
                checks={name:getattr(window,name).isChecked() for name in CHECK_FIELDS},
                mode=window.mode.currentText(),mode_b=window.mode_b.currentText(),budgets=[v.text() for v in window.budgets],
                bases=[v.value() for v in window.clock_bases],increments=[v.value() for v in window.clock_increments])


def apply_conditions(window,data):
    window.set_setup_source(None)
    for name in VALUE_FIELDS:
        if name in data['values']:getattr(window,name).setValue(data['values'][name])
    if 'play_pv_b' not in data['values'] and 'play_pv' in data['values']:
        window.play_pv_b.setValue(data['values']['play_pv'])
    for name in TEXT_FIELDS:getattr(window,name).setText(data['texts'][name])
    for name in CHECK_FIELDS:
        if name in data['checks']:getattr(window,name).setChecked(data['checks'][name])
    window.mode.setCurrentText(data['mode'])
    window.mode_b.setCurrentText(data.get('mode_b', 'Same as A'))
    for controls,key,method in [(window.budgets,'budgets','setText'),(window.clock_bases,'bases','setValue'),(window.clock_increments,'increments','setValue')]:
        for control,value in zip(controls,data[key]):getattr(control,method)(value)


def replay_openings(games):
    """Keep the saved pair order and opening moves, with fresh game results."""
    return [
        dict(fen=game['fen'], pair=game['pair'], a_white=game['a_white'],
             opening_plies=game.get('opening_plies', 0), opening_name=game.get('opening_name', ''),
             moves=game['moves'][:game.get('opening_plies', 0)], result='*')
        for game in games
    ]


def recorded_conditions(state):
    limits = [Limit(**value) for value in state['limits']]
    for limit in limits:
        limit.validate()
    rule = state.get('draw_rule', DEFAULT_RULE)
    sprt = state.get('sprt')
    values = dict(pairs=len({game['pair'] for game in state['games']}),
                  play_pv=playing_multipv(state, 0), play_pv_b=playing_multipv(state, 1),
                  clock_buffer=state.get('clock_buffer_seconds', 0.2),
                  draw_start=rule['after_move'], seed=state.get('seed', 0),
                  silence_timeout=state.get('silence_timeout_ms', 120000) // 1000)
    if sprt:
        values.update({f'sprt_{key}': sprt[key] for key in ('h0', 'h1', 'alpha', 'beta')})
    return dict(values=values, mode=limits[0].mode, mode_b=limits[1].mode,
                budgets=[str(limit.value) if limit.mode != 'clock' else '' for limit in limits],
                bases=[limit.value / 60000 if limit.mode == 'clock' else 10 / 60 for limit in limits],
                increments=[limit.increment_ms / 1000 if limit.mode == 'clock' else 0.1 for limit in limits],
                texts=dict(book=state.get('opening_book') or '', checkpoint=str(state.get('checkpoint', 1_000_000)),
                           maximum=str(state.get('maximum') or '')),
                checks=dict(auto_draw=rule['enabled'], sprt_enabled=bool(sprt),
                            keep_best_changes=state.get('save_best_changes', True),
                            randomized=state.get('randomized_openings', False)))


def local_profile_for_match(profiles, recorded):
    fingerprint = Profile(**recorded).fingerprint()
    for index, profile in enumerate(profiles):
        if profile.fingerprint() != fingerprint:
            continue
        try:
            if executable_hash(profile.path) == profile.identity and profile.network_files() == profile.networks:
                return index
        except (OSError, ValueError):
            continue
    return -1


def conditions_dialog(window):
    dialog=QDialog(window);dialog.setWindowTitle('Match presets');dialog.resize(520,200)
    layout=QVBoxLayout(dialog)
    note=QLabel('Save clocks, opening suite, pair count, search budgets and draw rules. Choose your engines separately. Applying a preset changes the next match setup.');note.setWordWrap(True);layout.addWidget(note)
    choices=QComboBox();layout.addWidget(choices)
    def refresh():
        choices.clear();choices.addItems(sorted(window.db.get('match_presets',{})))
    row=QHBoxLayout();layout.addLayout(row)
    def save():
        name,ok=QInputDialog.getText(dialog,'Save match preset','Preset name:')
        if not ok or not name.strip():return
        name=name.strip();presets=window.db.get('match_presets',{})
        if name in presets and QMessageBox.question(dialog,'Replace preset',f'Replace {name}?')!=QMessageBox.StandardButton.Yes:return
        presets[name]=capture_conditions(window);window.db.put('match_presets',presets);refresh();choices.setCurrentText(name)
    def apply():
        data=window.db.get('match_presets',{}).get(choices.currentText())
        if data:apply_conditions(window,data);dialog.accept()
    def delete():
        presets=window.db.get('match_presets',{});name=choices.currentText()
        if name and QMessageBox.question(dialog,'Delete preset',f'Delete {name}?')==QMessageBox.StandardButton.Yes:
            presets.pop(name,None);window.db.put('match_presets',presets);refresh()
    for text,action in [('Save current setup…',save),('Apply selected',apply),('Delete',delete),('Close',dialog.reject)]:
        control=QPushButton(text);control.clicked.connect(action);row.addWidget(control)
    refresh();dialog.exec()
