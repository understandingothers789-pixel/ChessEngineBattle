# Nocturne Engine Match & Analysis Studio

A standalone Python 3.12 / PySide6 desktop application built on the latest audited
Nocturne Chess implementation. No chess engines or NNUE networks are bundled.

## Build downloads

- [Download Nocturne Battle 0.1.0 for Windows](https://github.com/understandingothers789-pixel/ChessEngineBattle/actions/runs/42535154560/artifacts/13639565345) — successful GitHub Actions build. Sign in to GitHub to download; workflow artifacts expire. Extract the ZIP and run NocturneBattle.exe.

## Run from source (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\nocturne-battle
```

Git must be installed: the Nocturne dependency is pinned to audited commit
`5f9c69582039f42b743f2d12a4a28c188339e55d`. On Linux/macOS use
`.venv/bin/python` and `.venv/bin/nocturne-battle` instead. The original Nocturne
application and its database are untouched. Use this existing isolated checkout;
no Git worktree is required.

## Connect your engines and play

1. Choose **Add / clone engine profile**, browse to your own UCI executable,
   validate it, inspect discovered options, and save. Use JSON options such as
   `{"Threads": 1, "Hash": 64}`. Optional command arguments are a JSON array.
   Validate only executables you trust: validation launches the selected file.
2. Add another profile of the same executable or another engine. Select A and B.
3. Choose **nodes**, **depth**, or **movetime**. Movetime values are seconds;
   node/depth values are integers. No limit types are silently combined.
4. Choose a PGN/EPD opening suite, or leave blank for the starting position.
   Every opening pair uses the identical starting FEN with colors reversed.
   Set pair count (100 means 200 games), playing MultiPV (default 1), and the
   first checkpoint. The B:A node ratio presets apply in nodes mode.
5. Start, pause or resume the match. Each committed move and game result is saved.
   A paused/interrupted move restarts its search; previous observations retain
   their interrupted status. Do not run multiple copies on the same database.

Playing MultiPV >1 can affect strength. Supplementary analysis is a separate job
and never chooses tournament moves. Engines must advertise MultiPV for counts
above one; unavailable ranks are never fabricated. NNUE paths explicitly set via
EvalFile/EvalFileSmall/WeightsFile are hashed and checked for changes. Default
external networks selected internally by engines are not discoverable through
standard UCI; set those options explicitly for reproducible cache identity.

## Inspect what both engines thought

Select a game, navigate using arrows or the keyboard, then **Compare This
Position**. Cached results must match exact FEN, repetition path, executable hash,
network identity and engine settings. Profiles' playing histories usually refer
to different positions; absent data stays absent. Pause the match, choose explicit
budgets, then queue **A + B supplementary searches** for the selected position.
The queue is sequential and cancelable, and does not compete with match resources.

Both panels have independent stored-checkpoint selectors, labeled with requested
and actual reported nodes, provenance, MultiPV and completion status. Linked mode
selects an exact or explicitly approximate available target; ratio mode never
pretends that an unavailable 80M checkpoint is exact. A checkpoint match refers
to its **target**, not an exact engine node count. These are continuous-search
observations, not independent exact-budget results. Skipped doubling thresholds
are not synthesized. The original complete-rank capture gate is preserved.

Compare candidate overlap and ranking, best-move agreement, and selected PV
prefix/divergence. Choose each panel's PV rank. Scores preserve mate/cp/bounds and
can use White or side-to-move perspective. Hover a PV move for a legal board
preview, pin it, or enable dual boards for two simultaneous previews. Return to
Live resumes following the match without disturbing its execution.

Search Evolution shows stored checkpoint rows and an interactive log-node graph.
It excludes mate, missing and bound scores from its cp plot, labels its ±5-pawn
clipping, and never joins unrelated searches. Click a point or history row to
select that stored snapshot. Data remains available without restarting engines.

## Persistence and exports

Qt's per-user AppLocalDataLocation stores `battle.sqlite` (on Windows typically
`%LOCALAPPDATA%\Nocturne\NocturneBattle`). Engine profiles, layouts, settings,
searches and completed/interrupted histories persist. New matches archive the old
state rather than delete it; archived matches are included in JSON but currently
have no GUI match selector. Back up the database with the application closed.
A 2GB analysis ceiling stops additional capture rather than delete history.

JSON exports include all stored configuration, searches, statuses and snapshots.
CSV includes rank-level metadata as JSON plus position/search identity. PGN
exports current-match games and reproducibility headers; use JSON alongside PGN
for complete analysis histories. Executable paths and local settings are included
in exports, so review before sharing. Multithreaded engines and different hardware
can produce different searches even with the same recorded configuration.

## Tests and desktop packaging

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\pyinstaller --clean --noconfirm NocturneBattle.spec
```

Build on Windows to produce `dist\NocturneBattle\NocturneBattle.exe`. Keep the
whole directory, including Qt libraries, assets and licenses. The manually
runnable Windows GitHub Actions workflow runs tests and produces a build artifact.
The Windows 0.1.0 artifact above was produced by GitHub Actions; it has not been independently run on a Windows desktop. The mock UCI fixture is test-only and
is not included in the application bundle.

See [Nocturne audit](docs/NOCTURNE_AUDIT.md),
[engineering report](docs/ENGINEERING_REPORT.md), and
[third-party notices](THIRD_PARTY_NOTICES.md). This application is GPL-3.0-or-later.
