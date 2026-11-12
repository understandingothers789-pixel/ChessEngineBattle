# Chess Engine Battle changes

Download links and validation details are in [README.md](README.md#build-downloads).
New builds use the main branch; version numbers distinguish downloads.

## 0.5.4

- Show the strongest shared evaluation for drawn games in the game picker, with both engines’ scores and the move.

## 0.5.3

- Show the recorded draw or game-ending reason in the game picker and games table.

- Show each engine’s reported tablebase hits during live and recorded searches.

- Choose the move when automatic draw counting starts; the default is move 30.

- Add a clickable Live board evaluation graph for both engines using final recorded move searches, including saved games. Positive scores favor White.
- Automatic evaluation draw now defaults to ±0.30 pawns from move 30 for 10 consecutive plies. Existing matches retain their recorded rule.

## 0.5.2 rebuild 3 — recreated from 0.5.1

- Restore application and packaging from exact 0.5.1 source, then reapply only
  best-line history and version labels. Restore the original 0.5.1 workflow.
- File revision 0.5.2.2. Still unsigned; Smart App Control acceptance unverified.

## 0.5.2 rebuild 2

- Fresh Windows rebuild with the same packaging specification and pinned build
  tools recorded in the working 0.5.1 build; retains 0.5.2 best-line capture.
- Executable file revision is 0.5.2.1 to distinguish the rebuilt binary.
- Remains unsigned. CI startup/render validation does not establish acceptance
  by SmartScreen, Smart App Control or Defender on a downloaded file.

## 0.5.2

- Add Save previous best lines when the top move changes, enabled by default
  for new matches. Works with MultiPV 1 or higher and between node checkpoints.
- Keep every accepted top-move change, including same-depth changes and returns
  to an earlier move, with the old line's actual depth, score, nodes and full PV.
- Store events on completion or pause and include them in portable match files.
  Select Best change entries while reviewing a played move to preview the old line.

## 0.5.1

- Add shared tablebase setup and per-engine path summaries directly below Opening suite.
- Add More settings for A/B in Match Setup, opening tested engine options including Hash and Threads. Changes apply to the next match.

## 0.5.0 — Match Studio design

- Redesign the dark workspace with engine scorecards, distinct A/B accents,
  live clocks, completion progress and separate game/pair/Elo result cards.
- Replace the workspace dropdown with clear navigation and organize the toolbar
  around New match, Pause/Resume, Save copy and Match library. Engine loading
  lives on each engine's card; Reset view and tablebases stay visible.
- Add a first-match guide and numbered setup sections. Keep advanced position
  analysis tucked away until requested, and style engine and library dialogs.
- Frame live and recorded variations as focused cards with shorter metadata and
  clear game-result labels. Preserve complete recorded analysis and match files.
- Fit the workspace at 1280×800, grow the board at larger sizes, and allow the
  analysis side to scroll. Pane resizing and reset remain available.
- Add Ctrl+N (setup), Ctrl+O (library), Ctrl+Shift+S (save copy), and F9 (live).

## 0.4.2

- Make dark the default and add Reset view to restore pane sizes, compact
  variations, column fitting and live following without interrupting play.
- Keep a current-match game picker with Previous/Next game visible above the
  board, even when the table is hidden or resized.
- Show wins/losses/draws for both engines and completed color-reversed pairs,
  plus a rough game-score Elo difference. Incomplete pairs are excluded;
  undefeated or winless scores have no finite Elo estimate.
- Add Tablebases for both engines: select one Syzygy folder for missing paths,
  optionally replace existing paths, check advertised engine support and use
  up to five pieces. Saved profile changes apply to the next new match.

## 0.4.1

- Show a prominent A/B match score, wins and draws that follow the engines when
  colors reverse, including when reviewing saved tournaments.
- Add wider draggable horizontal/vertical pane dividers and retain pane sizes.
- Auto-fit game table columns, keeping Game/Pair/Plies narrow and long names
  compact. Fit columns resets sizing; drag or double-click header dividers to
  adjust individual columns. Hover cells for full text.
- Use pixel scrolling with larger scrollbar handles; retain table widths on restart.

## 0.4.0

- Default to short variation previews (3 full moves). Full variations remain
  available on demand and are always saved. Give more width and height to the board.
- Use a light slate and teal palette with a softer forest board and clearer
  running/paused/completed match progress.
- Add Save match for portable `.cebattle` files containing one tournament's
  games, results, clocks and all recorded engine searches, depths and checkpoints.
- Add Saved matches to browse the automatic library or open a portable file,
  choose a game and review the engine's thinking at any recorded move.
  Imported copies open for review without running engines or replacing history.

## 0.3.9

- Put the board and readable move list on the left and engine analysis on the
  upper right. Match setup opens separately; Pause/Resume stays in the top bar.
- Click any move to review its final MultiPV lines, earlier saved depths and
  checkpoints. Review stays fixed while the match continues. Follow live game
  returns to the current search. Hover variations for a floating board preview.
- Save complete MultiPV sets at reported search depths for new games, including
  short searches; restore saved analysis when reopening the app.
- Replace “Original thinking” with clear review wording, improve tooltips, and
  collapse the game list to leave more room for the board.

## 0.3.8

- Renamed the app to Chess Engine Battle, including its window, dialogs,
  Windows executable and download archive. Existing settings and games stay available.
- Brought all recent features and build notes onto main. Future automatic builds
  use main instead of creating a branch for each build.
- Kept the download history in the README and recorded the release process in
  the repository instructions.

## 0.3.7

- Show live MultiPV thinking on the right with hover previews; clicking a played
  move opens its recorded final search.
- Add manual and evaluation-based adjudication, plus automatic draw agreement
  after move 50 at ±0.20 pawns for ten consecutive plies.
- Distribute opening books separately from the application. Accept six-field FEN
  positions inside EPD opening files (included since 0.3.6).

Earlier versions and their change notes remain in the README's download history.
