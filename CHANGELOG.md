# Chess Engine Battle changes

Download links and validation details are in [README.md](README.md#build-downloads).
New builds use the main branch; version numbers distinguish downloads.

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
