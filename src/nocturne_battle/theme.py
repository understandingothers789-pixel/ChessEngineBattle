"""Light slate surfaces, teal actions, and clear match state."""
from nocturne.gui.theme import stylesheet as upstream_style


def stylesheet():
    return upstream_style(light=False) + '''
    QMainWindow, QDialog { background: #101820; }
    QGroupBox { background: #18232e; border: 1px solid #304452;
        border-radius: 10px; margin-top: 14px; padding: 10px; }
    QScrollArea, QTextBrowser, QPlainTextEdit { background: #18232e;
        border: 1px solid #304452; border-radius: 8px; }
    QPushButton { padding: 8px 12px; border-radius: 7px; }
    QPushButton#saveMatch, QPushButton#followLive { background: #237b6d; color: white; border: none; }
    QPushButton#saveMatch:hover, QPushButton#followLive:hover { background: #308e7e; }
    QLabel#matchBanner { background: #1e3837; color: #a6daca; padding: 10px; border-radius: 8px; }
    QLabel#matchScore { color: #b1e3d6; font-size: 17px; font-weight: 600; padding: 6px; }
    QSplitter::handle { background: #304452; border-radius: 4px; }
    QSplitter::handle:hover { background: #6cae9f; }
    QScrollBar:horizontal { height: 17px; background: #1e2c38; }
    QScrollBar:vertical { width: 17px; background: #1e2c38; }
    QScrollBar::handle:horizontal { min-width: 38px; background: #617d8c; border-radius: 5px; }
    QScrollBar::handle:vertical { min-height: 38px; background: #617d8c; border-radius: 5px; }
    QToolTip { background: #263746; color: #e2ecf4; border: 1px solid #536b79; padding: 7px; }
    '''
