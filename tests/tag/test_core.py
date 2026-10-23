from pathlib import Path
from ms_toolbox.tag.core import tag_combos

TEST_CSV_PATH = Path(__file__).parent / "test_data" / "test_tags.csv"

def test_success_tag_combos():
    result = tag_combos(TEST_CSV_PATH)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
    assert len(result) == 18