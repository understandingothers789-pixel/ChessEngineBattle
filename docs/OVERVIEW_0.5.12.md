# Chess Engine Battle overview — 0.5.12

## Current project

Chess Engine Battle is a local desktop match runner with two UCI engine profiles,
color-reversed opening pairs, independent clock controls and a configurable move
buffer. Engines and Syzygy files are supplied by the user. Match rules include
manual adjudication and consecutive completed-search evaluation agreement.

The live board and scorecards show current play. Historical review uses stored
playing searches, clock snapshots, MultiPV lines, depth history and best-move
changes. Evaluation plots and draw summaries use exact scores normalized to
White's perspective. The @ comparison requires lines that can be aligned to the
same position; it does not manufacture analysis at a shared position.

SQLite preserves local history; portable match files copy recorded games and
analysis into a review-only imported tournament. Graph data and scale caching
reduce repeated reads and per-point work. The library retains its historical
storage path so updates do not hide existing matches.

## Five candidate improvements

| Idea | Decision | Reason |
| --- | --- | --- |
| Named match-condition presets | Implemented | Makes repeated experiments easier to configure consistently. |
| Direct move navigation | Implemented | Makes a specific earlier position easier to find in a long game. |
| Move statistics export | Implemented | Makes recorded evaluations, nodes and timing available for spreadsheet analysis. |
| Engine health dashboard | Future | Would combine readiness, supported options, tablebase status and engine failures. |
| Statistical confidence estimates | Future | Would help users judge how much evidence a score or Elo estimate provides. |

## Implemented behavior

- A dedicated original knight icon replaces the generic executable/window icon.
  The ICO includes 16–256 pixel sizes and Windows taskbar grouping has a stable ID.
- Match Setup has a **Match presets** dialog. It saves clocks, buffer, opening
  path, pair count, search mode/budgets, MultiPV, checkpoint bounds and draw rules.
  Apply changes the next setup. Engine profiles and engine options are selected
  separately. Presets can be replaced or deleted with confirmation.
- **Go to move** lists the selected game's move numbers and notation, including
  the starting position. Choosing a move uses existing saved-analysis review.
- **Export move statistics** writes one row per recorded playing search for the
  selected game. Columns include color/engine side, final exact evaluation in
  White pawns, signed mate distance, depth, nodes, engine time, actual recorded
  elapsed time, post-move clock and tablebase hits. Missing fields remain blank;
  opening-book moves have no recorded playing search and are omitted.

## Checks and limits

The existing automated suite exercises match runtime, pause/resume, clocks,
profiles/options, opening imports, adjudication, tablebase configuration,
portable save/import, statistics, history and UI layout. New regression checks
cover preset round trips and exported score perspective and timing. The local
startup/render check passed. Windows CI additionally builds and starts the
packaged executable before the download is published.

No test suite establishes Smart App Control trust. Signing remains a separate
release task. Actual Syzygy probing and external-engine behavior depend on the
user's files; the optional real-engine test is skipped without an engine.
