from pathlib import Path
import pytest
from ms_toolbox.tag import TipoRequest, csv2tag, tag2nl

TEST_CSV_PATH = Path(__file__).parent / "test_data" / "test_tags.csv"
OUTPUT_DIR = Path(__file__).parent / "output"


def test_success_csv2tag():
    tag_strings = csv2tag(TEST_CSV_PATH)

    assert isinstance(tag_strings, list)
    assert all(isinstance(item, str) for item in tag_strings)
    assert len(tag_strings) == 4

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "csv2tag.txt").write_text("\n".join(tag_strings), encoding="utf-8")


@pytest.mark.tipo
def test_success_tag2nl():
    tag_strings = csv2tag(TEST_CSV_PATH)
    request = [TipoRequest(tags=t) for t in tag_strings]
    prompts = tag2nl(request)

    assert isinstance(prompts, list)
    assert all(isinstance(item, str) for item in prompts)
    assert len(prompts) == len(tag_strings)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "tag2nl.txt").write_text("\n\n---\n\n".join(prompts), encoding="utf-8")
