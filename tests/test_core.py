from pathlib import Path
from pdf_extract.core import get_total_pages, extract_and_save_pages

TEST_PDF_PATH = Path(__file__).parent / "test_data" / "Campbell-Biology-Chapter-1.pdf"

def test_success_get_total_pages():
    file_path = TEST_PDF_PATH
    result = get_total_pages(file_path)
    assert result == 25

def test_success_extract_and_save_pages(tmp_path):
    input_file_path = TEST_PDF_PATH
    output_file_path = tmp_path / "extracted_pages.pdf"
    start_page = 5
    end_page = 10

    result = extract_and_save_pages(input_file_path, output_file_path, start_page, end_page)

    assert result is True
    assert get_total_pages(output_file_path) == 6
