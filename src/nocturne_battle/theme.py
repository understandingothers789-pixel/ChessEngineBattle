"""Dark match studio palette, clear surfaces, and accessible actions."""
from nocturne.gui.theme import stylesheet as upstream_style


def _base_style():
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

# Studio surfaces use a restrained hierarchy: slate, mint, and per-engine accents.

def stylesheet():
    return _base_style() + '''
    QMainWindow, QDialog { background: #0c131e; }
    QWidget { font-size: 13px; }
    QLabel#studioTitle { color: #ecf2fb; font-size: 23px; font-weight: 700; letter-spacing: 1px; padding: 4px 0; }
    QLabel#sectionTitle { color: #e7effa; font-size: 19px; font-weight: 600; padding: 4px 0; }
    QLabel#eyebrow { color: #87acbd; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
    QLabel#muted, QLabel#cardDetail { color: #91a6bb; font-size: 12px; }
    QLabel#engineName { color: #e1eaf6; font-size: 14px; font-weight: 600; }
    QLabel#scoreValue { color: #74dfc3; font-size: 26px; font-weight: 600; }
    QFrame#engineCard[side="B"] QLabel#scoreValue { color: #9ab9ff; }
    QLabel#engineClock { color: #f3d798; font-size: 16px; font-weight: 600; }
    QLabel#resultValue { color: #d8e7f7; font-size: 24px; font-weight: 600; }
    QScrollArea#studioScroll { background: transparent; border: none; }
    QGroupBox#gamesDisclosure { padding: 0; margin-top: 12px; }
    QGroupBox#gamesDisclosure::title { padding: 0 4px; }
    QFrame#engineCard { background: #151f2d; border: 1px solid #2c3d50; border-top: 2px solid #438f82; border-radius: 12px; }
    QFrame#engineCard[side="B"] { border-top: 2px solid #6a8bc8; }
    QFrame#analysisCard { background: #131e2c; border: 1px solid #283a4f; border-radius: 12px; }
    QFrame#resultCard { background: #141f2d; border: 1px solid #293a4e; border-radius: 10px; }
    QLabel#analysisMetadata { color: #a8bfd1; font-size: 12px; }
    QFrame#analysisCard QScrollArea { background: transparent; border: none; }
    QPushButton { background: #1c2a3b; border: 1px solid #304156; border-radius: 8px; padding: 8px 14px; color: #d6e3f1; }
    QPushButton:hover { background: #293e53; border-color: #6c8ba5; }
    QPushButton:pressed { background: #334c61; }
    QPushButton:disabled { color: #64788b; background: #14202e; border-color: #233345; }
    QPushButton#primaryAction { background: #69d6b9; color: #08271f; font-weight: 600; border: none; }
    QPushButton#primaryAction:hover { background: #8de6cd; }
    QPushButton#boardNav { padding: 5px 10px; }
    QPushButton#engineLoad { background: transparent; border: none; color: #a9c6df; padding: 2px 4px; font-size: 11px; }
    QPushButton#engineLoad:hover { color: #8ce7cf; }
    QPushButton#navTab { background: transparent; border: none; color: #8ea4bc; padding: 7px 14px; }
    QPushButton#navTab:checked { background: #22374a; color: #b8f0df; border-bottom: 2px solid #69d6b9; border-radius: 5px; }
    QLabel#matchBanner { background: transparent; color: #a3b9c9; padding: 3px 0; font-size: 12px; }
    QProgressBar#matchProgress { min-height: 4px; max-height: 4px; background: #243344; border: none; border-radius: 2px; }
    QProgressBar#matchProgress::chunk { background: #64cfb3; border-radius: 2px; }
    QSplitter::handle { background: #223245; border-radius: 3px; }
    QSplitter::handle:hover { background: #67bdaa; }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #101c2b; border: 1px solid #34475c; border-radius: 7px; padding: 7px; selection-background-color: #316653; }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #6ed7bc; }
    QGroupBox { background: #141f2e; border: 1px solid #2d4054; padding: 14px; margin-top: 17px; }
    QGroupBox::title { color: #b7d2df; padding: 2px 6px; }
    QHeaderView::section { background: #203246; color: #b9ccdd; padding: 6px; border: none; border-right: 1px solid #2c4157; }
    QListWidget#matchLibrary { background: #111d2b; border: 1px solid #2d4054; border-radius: 10px; }
    QListWidget#matchLibrary::item { padding: 14px 12px; border-bottom: 1px solid #23374b; }
    QListWidget#matchLibrary::item:selected { background: #244b47; color: #e4fff6; }
    QTableView { background: #111d2b; alternate-background-color: #162637; border: 1px solid #2b3e53; gridline-color: #23374b; }
    QTableView::item:selected { background: #255e53; color: #e6fff8; }
    '''
