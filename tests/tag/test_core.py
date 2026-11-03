from pathlib import Path
from ms_toolbox.tag.core import tag_csv2str, tag_tag2nl, TipoRequest

TEST_CSV_PATH = Path(__file__).parent / "test_data" / "test_tags.csv"
OUTPUT_DIR = Path(__file__).parent / "output"

def test_success_tag_csv2str():
    tag_strings = tag_csv2str(TEST_CSV_PATH)
    
    assert isinstance(tag_strings, list)
    assert all(isinstance(item, str) for item in tag_strings)
    assert len(tag_strings) == 4

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "tag_csv2str.txt").write_text("\n".join(tag_strings), encoding="utf-8")

def test_success_tag2nl():
    tag_strings = tag_csv2str(TEST_CSV_PATH)
    request = [TipoRequest(tags=t) for t in tag_strings]
    reponse = tag_tag2nl(request)

    lines = [line for line in reponse.splitlines()]
    assert len(lines) == len(tag_strings)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "tag_tag2nl.txt").write_text(''.join(reponse), encoding="utf-8")