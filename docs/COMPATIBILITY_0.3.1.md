# 0.3.1 compatibility rebuild

The user reports original 0.3.1 runs, while 0.3.2/0.3.3 are blocked by Smart App
Control. Comparing the releases found no change to NocturneBattle.spec or the
runtime dependency declarations other than the application version. Windows
version resources and artifact labels advanced normally; no packaging cause for
the difference in Windows trust has been established.

This build uses the exact application source, spec and version resources from
commit ecc14156bf09362cd81dc68f7c61aa9e5b0c05a1. It is genuinely 0.3.1, not later
code relabeled as an earlier version. Later tooltips and performance/bug fixes
are absent. Latest development/0.3.0 source is preserved separately.

The workflow records Python/package versions, Authenticode status and SHA256 in
BUILD-INFO.txt in the artifact. Dependency ranges were not frozen in the original
build, so this is a source-baseline rebuild, not a proven byte-identical rebuild
of the previously accepted executable. No certificate/signing or Windows security
policy changes were made. Windows trust approval is not established by CI.

67 tests passed, one optional real-engine test skipped. Windows packaging,
packaged startup/render smoke and artifact upload all passed in run 42555590909.
No interactive Windows or real-engine validation was performed.

Build commit: 04babae0425d64c29c20fb6de9f3834520e41a80.
[Download compatibility build](https://github.com/understandingothers789-pixel/ChessEngineBattle/actions/runs/42555590909/artifacts/13647331434).
