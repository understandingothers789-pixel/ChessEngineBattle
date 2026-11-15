"""On-demand local engine and Syzygy configuration diagnostics."""
import os
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QPlainTextEdit,QPushButton,QLabel
from .model import executable_hash


def engine_report(profiles,state=None):
    rows=['ENGINE HEALTH / TABLEBASE DIAGNOSTICS', 'Local file checks only. Engine option support and actual tablebase probing are not verified here.']
    for side,profile in enumerate(profiles):
        rows.append(f'\nENGINE {"AB"[side]} · {profile.name}\nExecutable: {profile.path}')
        try:
            rows.append('Executable identity: '+('matches loaded profile' if executable_hash(profile.path)==profile.identity else 'CHANGED — reload and test this engine before starting a match'))
        except OSError as exc:rows.append('Executable unavailable: '+str(exc))
        opts={k.lower():v for k,v in profile.options.items()}
        rows.append(f'Configured Threads: {opts.get("threads","engine default")} · Hash: {opts.get("hash","engine default")} MB')
        path=str(opts.get('syzygypath',''))
        if not path or path=='<empty>':rows.append('Syzygy: no path configured');continue
        rows.append('Configured SyzygyPath: '+path)
        for part in path.split(';' if ';' in path or os.name=='nt' else os.pathsep):
            folder=Path(part)
            if not folder.is_dir():rows.append(f'  Missing folder: {part}');continue
            try:
                w=sum(1 for _ in folder.glob('*.rtbw'));z=sum(1 for _ in folder.glob('*.rtbz'))
                rows.append(f'  {part}: {w} WDL files, {z} DTZ files (top-level only; set completeness not verified)')
            except OSError as exc:rows.append('  Cannot inspect folder: '+str(exc))
        rows.append('Configured probe limit: '+str(opts.get('syzygyprobelimit','engine default')))
    if state:
        rows.append('\nRECORDED MATCH STATUS')
        rows.append(f'Game {min(state["index"]+1,len(state["games"]))}/{len(state["games"])}')
        for game in reversed(state['games']):
            if game.get('termination'):
                rows.append('Most recent ending: '+game['termination']);break
        rows.append('Tablebase hit counts reported by the engines appear in the live/recorded analysis. Zero hits alone does not prove a configuration problem.')
    return '\n'.join(rows)


def show_diagnostics(window):
    from .model import Profile
    dialog=QDialog(window);dialog.setWindowTitle('Engine health and tablebases');dialog.resize(760,540)
    layout=QVBoxLayout(dialog);note=QLabel('Inspect match engines while a match is loaded, or selected engines before a match. Refresh checks local files without starting engine searches.');note.setWordWrap(True);layout.addWidget(note)
    output=QPlainTextEdit();output.setReadOnly(True);layout.addWidget(output)
    def refresh():
        state=window.tournament.state
        profiles=[Profile(**p) for p in state['profiles']] if state else [window.profiles[c.currentIndex()] for c in window.engines if c.currentIndex()>=0]
        output.setPlainText(engine_report(profiles,state) if profiles else 'Load an engine first.')
    button=QPushButton('Refresh local checks');button.clicked.connect(refresh);layout.addWidget(button)
    close=QPushButton('Close');close.clicked.connect(dialog.accept);layout.addWidget(close)
    refresh();dialog.exec()
