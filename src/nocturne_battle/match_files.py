"""Portable tournament files; import copies IDs and never overwrites history."""
import json
import os
from pathlib import Path
from uuid import uuid4
from nocturne.core.game import Game
from .model import Profile, Limit


def write_match(db, state, path):
    data = db.export()
    game_ids = {g.get('id') for g in state['games']} - {None}
    searches = [r for r in data['searches'] if r.get('tournament') == state['id'] or r.get('game') in game_ids]
    ids = {r['id'] for r in searches}
    payload = dict(format='chess-engine-battle-match', version=1, tournament=state,
                   searches=searches, snapshots=[r for r in data['snapshots'] if r['id'] in ids])
    path = Path(path)
    if path.resolve() == db.path.resolve():raise ValueError('Choose a separate match file, not the active library database.')
    temporary = path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(payload),encoding='utf-8')
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def read_match(db, path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('format') != 'chess-engine-battle-match' or data.get('version') != 1:
        raise ValueError('Choose a Chess Engine Battle match file (.cebattle).')
    state = data['tournament']; searches = data['searches']; snapshots = data['snapshots']
    if not state['games'] or not 0 <= state['index'] <= len(state['games']):raise ValueError('Invalid match schedule')
    if len(state['profiles']) != 2 or len(state['limits']) != 2:raise ValueError('Invalid engine setup')
    for p in state['profiles']:Profile(**p)
    for limit in state['limits']:Limit(**limit).validate()
    for item in state['games']:
        game = Game(item['fen'])
        for move in item['moves']:game.play(game.board.parse_uci(move))
        if item['result'] not in ('*','1-0','0-1','1/2-1/2'):raise ValueError('Invalid result')
        if item.get('clock'):
            from .clocks import MatchClock
            MatchClock.restore(item['clock'])
    ids = {r['id'] for r in searches}
    if len(ids) != len(searches):raise ValueError('Duplicate search IDs')
    if any(r['id'] not in ids for r in snapshots):raise ValueError('Snapshot has no search')
    for item in state['games']:
        if any(link['search_run_id'] not in ids for link in item.get('move_searches',{}).values()):
            raise ValueError('Match file is missing a recorded move search')
    # New IDs preserve both the imported copy and any newer local version.
    mapping = {old:str(uuid4()) for old in ids | {state['id']} | {g['id'] for g in state['games'] if g.get('id')}}
    def remap(value):
        if isinstance(value,str):return mapping.get(value,value)
        if isinstance(value,list):return [remap(v) for v in value]
        if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
        return value
    data = remap(data); state = data['tournament']
    state['review_only'] = True
    with db.db:
        db.db.execute('INSERT INTO settings VALUES (?,?)',('tournament:'+state['id'],json.dumps(state)))
        for r in data['searches']:
            status = 'interrupted' if r['status'] == 'running' else r['status']
            db.db.execute('INSERT INTO searches VALUES (?,?,?,?,?,?)',
                (r['id'],r['position'],Profile(**r['profile']).fingerprint(),r['provenance'],status,json.dumps(r)))
        for r in data['snapshots']:
            db.db.execute('INSERT INTO snapshots VALUES (?,?,?)',(r['id'],str(r['requested']),json.dumps(r)))
    return state['id']
