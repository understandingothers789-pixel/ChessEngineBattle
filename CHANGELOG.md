# 0.5.29

- Give Chess Engine Battle a distinct two-rook icon on the Windows executable, taskbar, and window. Show the emblem beside the app title.

# 0.5.28

- Use a saved match as a new setup with its recorded opening order, rules, limits, and MultiPV. Verify matching local engine profiles before selecting them.
- Queue mixed match setups with a common opening schedule. Review each condition’s games, completed pairs, Elo, and interval in Experiments.
- Publish validated Windows ZIPs and SHA-256 checksums on versioned GitHub Releases. Support optional Authenticode signing through Azure Artifact Signing.

# 0.5.27

- Load engines and set each side’s clock, fixed search limit and MultiPV in the same setup panel.
- Apply a 20-second clock with 0.2 seconds per move from the clock preset menu. Node, depth and movetime fields start at 100K, 16 and 1 second and remember separate values per engine.

# 0.5.26

- Keep match presets and Review & start visible while scrolling through setup. Put each engine’s UCI settings beside its selector.
- Open the correct Results and Experiments panels from the main navigation. Show checkpoint comparison controls only where they apply.
- Search saved matches by engine, limits, MultiPV or opening book. Fit entries to the window and show search results as you type.
- Make move review controls readable at smaller sizes and show when a live match is running while you review.
- Group experiment actions together and make the results table read-only.

# 0.5.25

- Fresh Windows rebuild of 0.5.24 following a reported Smart App Control block.

# 0.5.24

- Saved matches display each engine’s search limit and MultiPV, the estimated A-minus-B Elo difference, and the opening book for newly created matches. Earlier matches without a recorded book say so.

# 0.5.23

- Engine cards show each side’s configured depth, node limit, clock or movetime and MultiPV.
- Clock is the default search mode for new setups. Search mode and budget tooltips explain clock, depth, nodes and movetime for each engine.

# 0.5.22

- Choose search modes independently. A clock-controlled engine can play an opponent using fixed depth or nodes. Only the timed side can lose on time, and its clock follows it when colors swap.

# 0.5.21

- Set playing MultiPV independently for Engine A and Engine B. Fixed depth and node matches support different search budgets and MultiPV values even when both sides select the same profile. Match presets retain both values.

# 0.5.20

- Use a pure Python solver for the SPRT calculation and remove SciPy and NumPy from the Windows package. This removes the NumPy extension named in the Application Control error.

# 0.5.19

- Fresh Windows rebuild for another installation attempt.

# 0.5.18

- Fresh Windows rebuild following an Application Control block of NumPy’s `_sfc64` extension. Includes the engine process isolation fix from 0.5.17.
- A successful build/startup check does not establish acceptance by a user’s Windows Application Control policy.

# 0.5.17

- Isolate process controllers when switching engine executables or arguments, disconnecting retired engine signals before starting the next search. Late shutdown events can no longer affect the replacement controller.
- Apply changed command-line arguments even when both profiles use the same executable.

# 0.5.16

- Preserve recent engine protocol and error output for a failed match search, and show it in engine diagnostics to help identify intermittent engine exits.
- Existing failures from earlier versions do not contain this new log. This update does not claim to fix the underlying exit.

# 0.5.15

- Refresh both engine dropdowns after editing profiles, preserve unloaded selections, and keep the original profile when choosing a different engine executable.
- Keep the other side’s selection correct when a profile is removed.

# Chess Engine Battle changes

Download links and validation details are in [README.md](README.md#build-downloads).
New builds use the main branch; version numbers distinguish downloads.

## 0.5.14

- Add normalized pentanomial generalized SPRT with preconfigured hypotheses, error rates, likelihood ratio, overshoot correction and persisted first decisions. Match schedule continues after a decision.
- Show normalized Elo and approximate 80/90/95/99% normalized intervals separately from logistic Elo.
- Numerical likelihood regression values checked against Fishtest.

## 0.5.13

- Add completed-pair pentanomial statistics, Elo intervals at 80/90/95/99%, standard error and approximate LOS in Results history.
- Group repeated openings and withhold intervals for insufficient or degenerate data. Fixed-sample approximation; not Fishtest SPRT.
- Add local engine identity, resource and Syzygy folder diagnostics.

## 0.5.12 rebuild

- Fresh Windows build with file revision 0.5.12.1.

## 0.5.12

- Add a dedicated knight icon for the executable, window and Windows taskbar.
- Save and reuse named match-condition presets in Match Setup.
- Jump directly to a recorded move and export final move statistics as CSV.
- Document the [overview and five implementation ideas](docs/OVERVIEW_0.5.12.md).

## 0.5.11 rebuild

- Fresh Windows build with file revision 0.5.11.1; retains the reliability fixes.

## 0.5.11 — reliability and usability review

- Honor the clock buffer during timeout checks and preserve actual recorded move time.
- Show both reviewed clocks consistently; clear stale divergence markers when changing saved searches.
- Label portable matches as review only and show draw/buffer settings in match confirmation.
- Cache the graph scale rather than recalculating it for each point.
- Add a [review report and improvement ideas](docs/REVIEW_AND_IDEAS.md).

## 0.5.10 rebuild

- Fresh Windows rebuild using the 0.5.9 packaging setup; file revision 0.5.10.1.

## 0.5.10

- Soften the main variation divergence highlight with a muted teal background.

## 0.5.9 rebuild 2

- Recreate from the 0.5.8 application and packaging baseline and reapply the recorded nodes and divergence highlight changes. File revision 0.5.9.2.

## 0.5.9 rebuild

- Fresh Windows rebuild with file revision 0.5.9.1, using the same packaging specification and workflow as the working 0.5.4 rebuild.

## 0.5.9

- Show recorded node counts for the selected engine search during move review.
- Highlight the divergence marker and move in recorded main variations.

## 0.5.8

- Show a persistent paused indicator in the toolbar; refresh reviewed clocks immediately. Cache graph data to reduce repeated database reads.

## 0.5.7

- Scorecard clocks follow the selected move during review and retain live ticking on the current live move.

## 0.5.6

- Add configurable 0.20-second default clock buffer and show active engine clock in live analysis.

## 0.5.5

- Show recorded move time and remaining clocks in move review. Mark the first main-line difference with @ when both lines can be aligned to the same position.

## 0.5.5

- Redesign the evaluation graph with an adaptive scale, move ticks, hover details, distinguishable engine lines and gaps for missing evaluations.

## 0.5.4 rebuild

- Rebuild using the working 0.5.2 packaging specification and Windows workflow. File revision 0.5.4.1; Smart App Control acceptance depends on Windows.

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
