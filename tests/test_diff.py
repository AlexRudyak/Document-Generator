from app.services.diff_service import calculate_diff


def test_unchanged_blocks_are_not_highlighted():
    old = [{"type": "paragraph", "text": "a"}]
    new = [{"type": "paragraph", "text": "a"}]
    result = calculate_diff(old, new)
    assert "_highlight" not in result[0]


def test_changed_text_is_highlighted():
    old = [{"type": "paragraph", "text": "a"}]
    new = [{"type": "paragraph", "text": "b"}]
    assert calculate_diff(old, new)[0]["_highlight"] is True


def test_appended_block_is_highlighted():
    old = [{"type": "paragraph", "text": "a"}]
    new = [{"type": "paragraph", "text": "a"}, {"type": "paragraph", "text": "c"}]
    result = calculate_diff(old, new)
    assert "_highlight" not in result[0]
    assert result[1]["_highlight"] is True
