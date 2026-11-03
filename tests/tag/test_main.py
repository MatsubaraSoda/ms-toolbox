import sys
import pytest
from pathlib import Path
from ms_toolbox.tag.main import cli_tag_csv2str, cli_tag_tag2nl

TEST_CSV_PATH = Path(__file__).parent / "test_data" / "test_tags.csv"
OUTPUT_DIR = Path(__file__).parent / "output"

def test_success_cli_tag_csv2str(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['tag-csv2str', '-i', str(TEST_CSV_PATH)])

    with pytest.raises(SystemExit) as exc_info:
        cli_tag_csv2str()

    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    output_text = captured.out

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "cli_tag_csv2str.txt").write_text(output_text, encoding="utf-8")

def test_success_cli_tag_tag2nl(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "tag-tag2nl",
        "-t", "1girl, standing, tachi-e", "1girl, lying, on_back",
        "--dry-run"
    ])

    with pytest.raises(SystemExit) as exc_info:
        cli_tag_tag2nl()

    assert exc_info.value.code == 0