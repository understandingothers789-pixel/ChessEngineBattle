import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import pytest
from nocturne_battle.model import Database, Profile, executable_hash


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path/'battle.sqlite')
    yield database
    try:
        database.close()
    except Exception:
        pass


@pytest.fixture
def profile():
    return Profile('Mock A', sys.executable, {'Threads': 1, 'Hash': 64},
        [str(Path(__file__).parent/'fixtures/mock_uci.py')], executable_hash(sys.executable),
        'Nocturne deterministic fixture')
