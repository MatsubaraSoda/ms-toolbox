import sys
import pytest
from pathlib import Path
from pdf_isolate.main import main

TEST_PDF_PATH = Path(__file__).parent / "test_data" / "Campbell-Biology-Chapter-1.pdf"

def test_success_main(monkeypatch, tmp_path):
    input_file_path = TEST_PDF_PATH
    output_file_path = tmp_path / 'output.pdf'
    monkeypatch.setattr(sys, 'argv', ['main.py', '-i', str(input_file_path), '-o', str(output_file_path), '--start', '5', '--end', '10'])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0