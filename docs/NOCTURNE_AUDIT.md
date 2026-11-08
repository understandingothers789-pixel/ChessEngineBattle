# Nocturne audit, before architecture changes

Audited upstream main at 5f9c695 (0.5.7.148), including 5297a04 and ef509bf.
The original checkout is preserved, unmodified. No binaries are bundled.

## Two systems, not one

* `snapshots.py:milestones` and `gui/engine.py:_observe/_flush_snapshot` implement
  **1/2/5 × powers of ten**, continuous engine-reported observations. Pending
  milestones can share one observation. `storage.py:analysis_snapshots` persists
  these in SQLite by game, path-derived position key, and milestone.
* `gui/analysis_history.py:AnalysisHistory.observe` implements **doubling**, starting
  at 1M without an upper limit. It advances through crossed thresholds but records
  only the highest crossed one. Records are immutable deep copies of current PV
  lines; different ranks may have different depths. This history is an in-memory
  OrderedDict, limited to 128 positions; a new session clears that position's
  checkpoints. It does **not** survive a restart. Precise history uses stopped,
  separate searches in `gui/window.py`, which are distinct from continuous capture.

Therefore the requested persistent doubling system is only partially present in
current upstream. Battle extracts the doubling algorithm into `history.py`, with
configurable bounds, and persists its output. It does not use the older 1/2/5
collector or invent outputs for skipped thresholds. Tests cover the original
highest-crossed semantics. The source application is not changed.

## Reuse and boundaries

Installed, pinned Nocturne modules are imported directly, not forked: core Game
and Board (legal moves, SAN, FEN, game tree, PGN), EngineController and UciConnection,
UCI score/option parsers, BoardWidget and piece assets, CandidatePanel, MoveText,
EvaluationBar and theme stylesheet. No alternate rules, board, transport or PV
renderer is implemented. The new pure doubling collector is shared by live play
and supplementary searches.

UciConnection uses asynchronous QProcess, bounded output, handshake timeouts,
readiness/stop barriers and generation IDs to reject stale output on position
changes. EngineController validates/truncates PVs to legal moves, caches SAN,
and separates mate/cp scores, bounds, seldepth, time and NPS. Battle observes raw
unthrottled info via that connection, validates using the same controller, and
stores rank-specific reported nodes. CandidatePanel previews give rank/ply;
BoardWidget.show_preview receives a legally replayed board. Dual preview boards
have separate states; pinning prevents mouse leave from resetting a board.
EvaluationBar is on the right. Both panels format scores from White's perspective.

## Correctness improvements and architecture

Upstream's path-based position key is useful for study nodes but does not encode
engine identity/settings; persisted milestones can collide across profiles.
Battle uses separate SQLite tables and indexed keys including full canonical FEN
(including counters and literal EP), initial FEN + move history (repetition),
executable SHA256, discovered version, options, MultiPV, limit, and provenance.
Game/tournament/search IDs are retained; no historic results are silently evicted.
Each snapshot distinguishes requested checkpoint, actual reported nodes,
per-rank nodes and completeness; Nocturne’s complete-rank gate is preserved, so a search that never reports all requested ranks has no checkpoints and is marked completed-incomplete; interruption changes search status, not results.
A database byte ceiling blocks additional captures rather than silently deleting
history. Supplementary jobs are explicit, sequential and isolated from play.

This first vertical slice covers sequential paired matches, local engine profiles,
PGN/EPD openings, durable resume, stored same-position comparisons, independent,
linked and ratio checkpoint selection, PV previews, and basic evolution/export.
Advanced statistical inference, SPRT, Polyglot, parallel tournaments, automatic
milestones and Windows installer publishing remain separate work.
