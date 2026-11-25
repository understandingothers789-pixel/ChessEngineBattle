# Chess Engine Battle UI review

The review followed the workflow from engine selection through match setup, live play, game review, results, saved matches and node-scaling experiments. A temporary library with several Stockfish matchups exercised the screens with repeated engine names, independent search limits and partially completed matches. The compact layout was checked at 1280 × 800, with Match Setup also checked at 620 × 590.

| Area | Finding | Change in 0.5.26 |
| --- | --- | --- |
| First launch and engine profiles | Live analysis controls appeared before a game existed. Separate full-width engine settings buttons made it harder to see which profile they edited. | The first-match guide takes focus until a match exists. Each engine selector has its own Settings button. |
| Match setup | Starting a match or applying a preset required scrolling. An invalid opening suite could fail after the start confirmation. | Presets, Close and Review & start stay at the bottom. The opening suite and game schedule are checked before confirmation. |
| Live board and review | Move action text was clipped at the smaller window size. The interface gave little indication that a user reviewing a move had stopped following the running board. | Move actions fit their text. Move arrows have accessible names and stop at the first or last position. Review mode shows when the match is still running and enables Return to Live. The game picker and Reset view remain accessible. |
| Results and advanced analysis | Results and Experiments went to the wrong tabs. Comparison settings appeared across unrelated pages. | Navigation opens each named panel. Search comparison, search history, evaluation by move and candidate rankings are grouped under Advanced analysis. The node ratio field appears when node-ratio lock is selected. |
| Saved matches | Long entries required horizontal scrolling, and similar configurations were difficult to locate. | Search by engine, depth, nodes, MultiPV or book. Entries wrap and put the two engine conditions next to each other above the A-minus-B Elo estimate. No-results and empty-library states explain why the list is empty. |
| Experiments | Four full-width actions competed with the chart and table. Clicking a cell could open a condition while trying to inspect the numbers. | Actions share a compact row and reflect the experiment state. Results are read-only, with double-click or Enter to open a condition. |

The local checks cover navigation, match filtering and opening the correct saved match, review during live play, and resizing with the game picker accessible. Windows CI runs the full test suite and packaged startup check. Desktop layout inspection used Qt rendering on Linux.
