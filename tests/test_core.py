import pytest
from pathlib import Path
from pdf_extract.core import get_total_pages

def test_success_get_total_pages():
    path = Path(__file__).parent / "test_data" / "Campbell-Biology-Chapter-1.pdf"
    result = get_total_pages(str(path))
    assert result == 25