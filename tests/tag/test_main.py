import sys
import pytest
from pathlib import Path
from ms_toolbox.tag.main import main

TEST_CSV_PATH = Path(__file__).parent / "test_data" / "test_tags.csv"

def test_success_main(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['main.py', '-i', str(TEST_CSV_PATH)])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0