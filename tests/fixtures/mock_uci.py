"""Deterministic test protocol peer. Not a chess engine for tournament use."""
import sys
import chess

board = chess.Board()
multipv = 1
incomplete = '--incomplete' in sys.argv
score_override = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--score-cp=')), None)
for raw in sys.stdin:
    line = raw.strip()
    if line == 'uci':
        print('id name Nocturne deterministic fixture')
        print('option name MultiPV type spin default 1 min 1 max 5')
        print('option name Threads type spin default 1 min 1 max 16')
        print('option name Hash type spin default 64 min 1 max 1024')
        if '--syzygy' in sys.argv:
            print('option name SyzygyPath type string default <empty>')
            print('option name SyzygyProbeLimit type spin default 7 min 0 max 7')
        print('uciok', flush=True)
    elif line == 'isready':
        print('readyok', flush=True)
    elif line.startswith('setoption name MultiPV value '):
        multipv = int(line.split()[-1])
    elif line.startswith('position fen '):
        tail = line[len('position fen '):].split(' moves ')
        board = chess.Board(tail[0])
        if len(tail) > 1:
            for move in tail[1].split():
                board.push_uci(move)
    elif line.startswith('go'):
        if '--crash' in sys.argv:
            import os
            os._exit(7)
        if '--illegal' in sys.argv:
            print('bestmove e2e5',flush=True);continue
        if '--silent' in sys.argv:continue
        if '--no-info' in sys.argv:
            print('bestmove '+next(iter(board.legal_moves)).uci(),flush=True);continue
        if '--wait' in sys.argv:
            import time
            time.sleep(0.2)
        moves = sorted(board.legal_moves, key=lambda m: m.uci())
        tokens = line.split()
        limit = int(tokens[tokens.index('nodes')+1]) if 'nodes' in tokens else 8_000_000
        for nodes in [500_000, 1_100_000, 5_000_000, 8_100_000]:
            if nodes > limit and nodes != 500_000:
                continue
            for rank, move in enumerate(moves[:1 if incomplete else multipv], 1):
                pv = [move.uci()]
                after = board.copy()
                after.push(move)
                for _ in range(3):
                    replies = sorted(after.legal_moves, key=lambda m: m.uci())
                    if not replies:
                        break
                    reply = replies[0]
                    pv.append(reply.uci())
                    after.push(reply)
                score = 25-rank if score_override is None else score_override
                depth = {500_000:4,1_100_000:8,5_000_000:10,8_100_000:12}[nodes] if '--depth-evolution' in sys.argv else 12
                print(f'info depth {depth} seldepth 18 multipv {rank} score cp {score} nodes {nodes} nps 2000000 time 100 pv {" ".join(pv)}', flush=True)
        print('bestmove ' + (moves[0].uci() if moves else '0000'), flush=True)
    elif line == 'stop':
        moves = sorted(board.legal_moves, key=lambda m: m.uci())
        print('bestmove ' + (moves[0].uci() if moves else '0000'), flush=True)
    elif line == 'quit':
        break
