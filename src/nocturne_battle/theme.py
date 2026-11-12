"""Light slate surfaces, teal actions, and clear match state."""
from nocturne.gui.theme import stylesheet as upstream_style


def stylesheet():
    return upstream_style(light=True) + '''
    QMainWindow, QDialog { background: #eef3f6; }
    QGroupBox { background: #ffffff; border: 1px solid #d9e3e9;
        border-radius: 10px; margin-top: 14px; padding: 10px; }
    QScrollArea, QTextBrowser, QPlainTextEdit { background: #ffffff;
        border: 1px solid #dce5eb; border-radius: 8px; }
    QPushButton { padding: 8px 12px; border-radius: 7px; }
    QPushButton#saveMatch, QPushButton#followLive { background: #237b6d; color: white; border: none; }
    QPushButton#saveMatch:hover, QPushButton#followLive:hover { background: #308e7e; }
    QLabel#matchBanner { background: #e0eeea; color: #245e53; padding: 10px; border-radius: 8px; }
    QLabel#matchScore { color: #174e47; font-size: 19px; font-weight: 600; padding: 6px; }
    QSplitter::handle { background: #d2dfe5; border-radius: 4px; }
    QSplitter::handle:hover { background: #79b4a6; }
    QScrollBar:horizontal { height: 17px; background: #e5edf2; }
    QScrollBar:vertical { width: 17px; background: #e5edf2; }
    QScrollBar::handle:horizontal { min-width: 38px; background: #91a8b5; border-radius: 5px; }
    QScrollBar::handle:vertical { min-height: 38px; background: #91a8b5; border-radius: 5px; }
    QToolTip { background: #fffdf6; color: #253447; border: 1px solid #d9dfd6; padding: 7px; }
    '''
