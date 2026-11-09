# Third party components

Nocturne Chess 0.5.7.148, commit 5f9c69582039f42b743f2d12a4a28c188339e55d,
https://github.com/understandingothers789-pixel/nocturne-chess
Copyright (c) 2026 Nocturne Chess contributors.
Distributed package metadata declares GPL-3.0-or-later; COPYING is included.
The doubling collector is extracted from AnalysisHistory.observe and its window
complete-rank gate. Other Nocturne components are dependencies imported directly.
Its package assets and their notices remain part of the installed distribution.
Consult upstream THIRD_PARTY_NOTICES.md for piece/font asset attribution.

python-chess / chess 1.11.2: GPL-3.0-or-later, https://python-chess.readthedocs.io
PySide6 / Qt for Python 6.8.3: LGPL-3.0/GPL/commercial,
https://doc.qt.io/qtforpython-6/licenses.html. Dynamic Qt libraries are included
by PyInstaller; retain its collected license files when redistributing.
PyInstaller's bootloader exception allows packaged application redistribution.

No Stockfish, NNUE network, Maia model, or other engine executable is included.
Test fixtures speak UCI deterministically and are not playing-strength engines.

Bundled opening suites: official-stockfish/books, CC0 1.0 Universal.
https://github.com/official-stockfish/books . Upstream names and counts are
preserved; books/LICENSE.txt contains the license, books/README.txt provenance.
