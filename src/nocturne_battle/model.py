"""Durable profiles, exact-position analysis and resumable paired schedules."""
from dataclasses import dataclass, asdict, field
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import sqlite3
import time
from uuid import uuid4

import chess
import chess.pgn


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def executable_hash(path):
    with open(path, 'rb') as stream:
        return sha256(stream.read()).hexdigest()


def position_identity(game):
    # Keep counters and repetition path as well as literal EP: conservative cache reuse.
    fen = game.board.native.fen(en_passant='fen')
    return digest([fen, game.initial_fen, [m.uci() for m in game.moves[:game.cursor]]])


@dataclass
class Profile:
    name: str
    path: str
    options: dict = field(default_factory=lambda: {'Threads': 1, 'Hash': 64})
    arguments: list = field(default_factory=list)
    identity: str = ''
    engine_name: str = ''
    id: str = field(default_factory=lambda: str(uuid4()))
    networks: dict = field(default_factory=dict)

    def network_files(self):
        files = {}
        for name, value in self.options.items():
            if name.lower() in ('evalfile', 'evalfilesmall', 'weightsfile') and value:
                path = Path(value)
                if not path.is_absolute():
                    path = Path(self.path).parent / path
                files[str(path.resolve())] = executable_hash(path)
        return files

    def fingerprint(self):
        return digest([self.identity, self.engine_name, self.options, self.arguments, self.networks])


@dataclass
class Limit:
    mode: str = 'nodes'
    value: int | float = 1_000_000

    def validate(self):
        if self.mode not in ('nodes', 'depth', 'movetime') or not math.isfinite(self.value) or self.value <= 0:
            raise ValueError('Choose a positive nodes, depth or movetime limit')
        if self.mode in ('nodes', 'depth') and int(self.value) != self.value:
            raise ValueError('Nodes and depth must be integers')
        if self.mode == 'depth' and self.value > 128:
            raise ValueError('Depth must be at most 128')


def openings(path):
    if not path:
        return [chess.STARTING_FEN]
    result = []
    with open(path, encoding='utf-8-sig') as stream:
        if Path(path).suffix.lower() == '.pgn':
            while (game := chess.pgn.read_game(stream)) is not None:
                if game.errors:
                    raise ValueError(f'Invalid PGN: {game.errors[0]}')
                board = game.end().board()
                result.append(board.fen(en_passant='fen'))
        elif Path(path).suffix.lower() == '.epd':
            for line in stream:
                if line.strip() and not line.lstrip().startswith('#'):
                    board = chess.Board()
                    board.set_epd(line.strip())
                    result.append(board.fen(en_passant='fen'))
        else:
            raise ValueError('Select a PGN or EPD opening suite')
    if not result:
        raise ValueError('Opening suite is empty')
    if any(not chess.Board(f).is_valid() or chess.Board(f).is_game_over() for f in result):
        raise ValueError('Opening suite contains invalid or terminal positions')
    return result


def schedule(fens, pairs, seed=0, randomized=False):
    if pairs < 1 or not fens:
        raise ValueError('At least one opening and pair are required')
    choices = list(fens)
    if randomized:
        random.Random(seed).shuffle(choices)
    return [dict(fen=choices[i % len(choices)], pair=i, a_white=a_white,
                 moves=[], result='*') for i in range(pairs) for a_white in (True, False)]


class Database:
    def __init__(self, path, max_bytes=2_000_000_000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS searches(id TEXT PRIMARY KEY, position TEXT NOT NULL,
            profile TEXT NOT NULL, provenance TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS search_lookup ON searches(position,profile,provenance);
          CREATE TABLE IF NOT EXISTS snapshots(search TEXT NOT NULL, checkpoint TEXT NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(search,checkpoint));
        ''')

    def put(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

    def get(self, key, default=None):
        row = self.db.execute('SELECT payload FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def begin(self, game, profile, limit, multipv, provenance, tournament=None):
        sid = str(uuid4())
        context = dict(id=sid, position=position_identity(game), fen=game.board.native.fen(en_passant='fen'),
                       initial_fen=game.initial_fen, moves=[m.uci() for m in game.moves[:game.cursor]],
                       game=game.id, tournament=tournament, profile=asdict(profile),
                       fingerprint=profile.fingerprint(), limit=asdict(limit), multipv=multipv,
                       provenance=provenance, kind='continuous', timestamp=time.time())
        with self.db:
            self.db.execute('INSERT INTO searches VALUES (?,?,?,?,?,?)',
                            (sid, context['position'], profile.fingerprint(), provenance, 'running', json.dumps(context)))
        return context

    def capture(self, context, snapshot):
        used = sum(p.stat().st_size for p in self.path.parent.glob(self.path.name+'*') if p.is_file())
        if used >= self.max_bytes:
            raise ValueError('Analysis storage limit reached; export and explicitly remove history first')
        record = context | snapshot
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?)',
                            (context['id'], str(record['requested']), json.dumps(record)))

    def finish(self, sid, status):
        with self.db:
            self.db.execute('UPDATE searches SET status=? WHERE id=?', (status, sid))

    def recover(self):
        with self.db:
            self.db.execute("UPDATE searches SET status='interrupted' WHERE status='running'")

    def records(self, game, profile, multipv=None):
        rows = self.db.execute('''SELECT snapshots.payload, searches.status FROM snapshots
          JOIN searches ON searches.id=snapshots.search WHERE searches.position=? AND searches.profile=?
          ORDER BY searches.rowid, snapshots.rowid''', (position_identity(game), profile.fingerprint()))
        records = [json.loads(payload) | {'status': status} for payload, status in rows]
        return [r for r in records if multipv is None or r['multipv'] == multipv]

    def export(self):
        return dict(settings={k: json.loads(v) for k, v in self.db.execute('SELECT * FROM settings')},
                    searches=[json.loads(p) | {'status': s} for s, p in self.db.execute('SELECT status,payload FROM searches')],
                    snapshots=[json.loads(p) for (p,) in self.db.execute('SELECT payload FROM snapshots')])

    def close(self):
        self.db.close()
