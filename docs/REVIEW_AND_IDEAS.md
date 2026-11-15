# Reliability and usability review — 0.5.11

Reviewed the clock accounting and timeout path, pause/resume state, historical
move navigation, final/depth/checkpoint analysis, divergence rendering, graph
loading and rendering, saved match handling, and match setup. The automated
suite also covers UCI integration with deterministic engines, import/export,
opening suites, adjudication, tablebase configuration, statistics, and layout.

## Fixes

- The expiry timer now honors the same buffer as move receipt. Previously it
  could forfeit the engine before its configured allowance had expired.
- Recorded elapsed time remains actual elapsed time rather than time after
  deducting the buffer. Old recorded values cannot be reconstructed.
- Review uses both sides of the most recent clock snapshot and formats clocks
  consistently as minutes and seconds. Move zero uses a saved pre-search clock
  when available; absent history is displayed as unavailable.
- Changing recorded depth/checkpoint recalculates divergence and removes stale
  markers. Starting a live search removes the old review marker.
- Imported portable matches identify themselves as review only rather than paused.
- The graph no longer recomputes its scale for each plotted point. It also no
  longer overrides QWidget.geometry with an unrelated plotting rectangle.
- Clock tooltips explain review versus live time. Match confirmation includes
  the buffer and automatic draw settings.

## Prioritized ideas

1. **Trusted signed Windows releases:** establish a signing service and durable
   GitHub Releases downloads to reduce repeated Smart App Control problems.
2. **Match health panel:** engine readiness, tablebase configuration, recent TB
   hits, and explicit reasons for an engine timeout or missing evaluation.
3. **Setup presets:** save named engine/time/book/rule combinations and provide
   beginner presets with resource estimates.
4. **Review timeline:** display eval, clock, nodes and depth together, with
   clickable swings and a synchronized move table.
5. **Better result statistics:** confidence intervals, pentanomial pair scores,
   and enough-games guidance beside the rough Elo estimate.
6. **Match library management:** rename, tag, search, compare and archive runs;
   add automatic backup rotation and storage usage estimates.
7. **Comparison at the same position:** optional supplementary analysis by both
   engines at a selected position, clearly distinguished from original searches.
8. **Accessibility settings:** font scaling, keyboard navigation guide and
   configurable colors for engine lines and divergence.

## Validation

The local full suite passed with 125 tests and one optional real-engine skip.
An additional divergence regression check passed afterward, and the local
application startup/render smoke check passed. Windows CI passed all 126 tests with one optional real-engine skip and the
packaged executable startup/render check.

## Limits

Automated tests cannot establish Smart App Control approval, physical Windows
interaction quality, or tablebase correctness without the user's actual engine
and Syzygy files. No universal bug-free guarantee is possible. The optional
real-engine integration check is skipped when no external engine is configured.
