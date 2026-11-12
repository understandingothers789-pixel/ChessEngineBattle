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
    QToolTip { background: #fffdf6; color: #253447; border: 1px solid #d9dfd6; padding: 7px; }
    '''
