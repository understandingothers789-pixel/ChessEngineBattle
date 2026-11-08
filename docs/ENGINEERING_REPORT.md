# Engineering report — first working vertical slice

## Foundation and architecture

Audited latest Nocturne main, 5f9c69582039f42b743f2d12a4a28c188339e55d
(0.5.7.148). Original source checkout and application remain unmodified.
See NOCTURNE_AUDIT.md for the important difference between persisted 1/2/5
milestones and the newer in-memory doubling history.

Reuse via an immutable Git dependency: Game/Board/rules, BoardWidget with original
assets and inside coordinates, right-side EvaluationBar, CandidatePanel/MoveText
with original PV formatting/hover signals, EngineController/UciConnection with
QProcess stop barriers, UCI parsers and score formatting, and native theme.
Doubling capture is extracted into history.py, preserving the complete-rank gate,
highest-crossed threshold and frozen observations; both live and supplementary
searches use it. Regression tests compare its output with Nocturne itself.

New modules:

- model.py: SQLite WAL persistence, profiles and executable/network hashes,
  exact-position/history identity, immutable search context, opening validation,
  deterministic color-reversed scheduling and bounded capture storage.
- runtime.py: generation-scoped search lifecycle and sequential resumable matches.
- app.py: native resizable desktop, engine discovery/manager, live/history
  navigation, comparisons, preview routing/pinning, evolution graph and export.

## Implemented and exercised

Local engine discovery and option validation; separate profiles of the same
executable; fixed nodes/depth/movetime with exclusive UCI commands; ratio presets;
PGN/EPD opening suites; seeded random ordering and exact color-reversed pairs;
playing MultiPV 1–5; asynchronous sequential matches, pause and restart recovery;
continuous doubling checkpoints above 1B; exact target vs actual reported nodes;
complete-rank gate with honest missing data; durable settings, match state,
search provenance, interruptions and snapshots.

Both panels retrieve compatible data for the exact selected position, retain
independent selections, synchronize targets or link a node ratio with explicit
approximation. Candidate overlap, ranking changes, unique moves, best-move
agreement, selected-PV shared prefix/divergence are displayed. Score types and
bounds are preserved; perspective can switch. Original PV hover rendering drives
shared or separate boards with pins. Explicit supplementary jobs run only with
match resources paused; they are tagged separately during a match or post-game.
No expensive searches are launched on navigation.

The log-node evolution graph and table select stored snapshots without searches.
JSON preserves the whole database's configuration/analysis records; CSV preserves
rank metadata; PGN exports the current match with reproducibility headers. New
matches archive old state rather than delete it. Persistent storage is per user,
separate from Nocturne's library. A 2GB ceiling blocks capture instead of silently
deleting history.

## Validation evidence

30 tests pass on Python 3.12 / PySide6 6.8.3 in Linux offscreen Qt. Tests execute
deterministic UCI subprocesses, not bundled real engines. Coverage includes:
registration/discovery; self-play profiles; node/depth/time command integrity;
MultiPV 1–5; complete/incomplete output; skipped checkpoints; freezing; upstream
algorithm equivalence; >1B doubling; storage reopening and interrupted recovery;
cache identity and external network changes; same-position guard; seeded opening
pairs; terminal paired tournaments; mid-match pause/resume; canceled stale output;
event-loop progress during search; GUI render, independent selectors, hover,
dual boards and pinning; actual JSON/CSV/PGN files parsed after export.

`pip install -e '.[dev]'` succeeded with the pinned upstream Git dependency;
`pip check` found no broken requirements. PyInstaller built a Linux desktop
bundle; its offscreen `--smoke-test` rendered the window and exited successfully.
Final source is tested after UI adjustments. Linux validates the shared logic,
not native Windows executable behavior or playing strength.

## Remaining limitations (not a completed five-phase roadmap)

- No base-plus-increment clocks, independent clock presets, concurrent tournament
  workers, SPRT, Elo confidence intervals, grouped statistics, or automatic
  discovery-milestone detection. Results currently show W/L/D and score only.
- No Polyglot, metadata evaluation filtering, opening preview board or recent-book
  menu. PGN/EPD validate into start FENs; PGN opening move history is not retained
  for pre-start repetition adjudication (identical FEN still used for each pair).
- Snapshots are continuous observations; there is no exact independent-budget
  result mode, final-result fallback checkpoint, or synthetic skipped threshold.
  Engines that never provide all requested ranks produce no checkpoint and their
  search is labeled completed-incomplete. Per-rank depths/nodes can differ.
- Comparison reports prefix/divergence and overlap in text; it does not yet
  highlight arbitrary selected-line divergence inside both PV renderers. Graphs
  exclude mate/bounds/missing scores, clip cp to ±5 pawns and label that clipping.
- The queue supports selected positions, not automatic whole-game batching.
  Interrupted searches restart rather than resume engine internal state.
- Storage has a fixed safety ceiling configurable through Database(max_bytes),
  but no GUI cleanup/retention editor. Archived matches remain in JSON/SQLite but
  lack an archive-browser UI. One application instance per database is expected.
- Standard UCI does not expose executable-selected default NNUE file identity;
  explicitly configure EvalFile/EvalFileSmall/WeightsFile for hashed external
  network identity. Other engine-specific external resources need explicit
  integration. Cache keys conservatively distinguish repetition paths/counters.
- Native Windows build, real-engine compatibility/strength, long 200-game soak
  tests, accessibility review and installer signing have not been performed.
  No release artifact has been published. The existing CI workflow can build a
  Windows artifact; only an actually successful build should get a download link.

## Windows and connecting engines

Use Python 3.12, Git and README's PowerShell commands. Run tests then
`pyinstaller --clean --noconfirm NocturneBattle.spec` on Windows. Distribute the
entire dist/NocturneBattle directory and its licenses; no engine/model binaries
are included. Add your own UCI executable through Add / clone engine profile,
validate its options, and create a second independent profile as needed.
