"""Revision diffing for document blocks.

When a document is regenerated from a parent revision, we mark which blocks
changed so the PDF engine can highlight them (yellow background).
"""


def calculate_diff(old_blocks, new_blocks):
    """Return ``new_blocks`` with a ``_highlight`` flag on changed/added blocks.

    This is a *positional* comparison: block ``i`` in the new list is compared to
    block ``i`` in the old list by ``type`` and ``text``. A block is highlighted
    when it differs from the block at the same index, or when it has no
    counterpart (the new document is longer). Consequence: inserting or deleting a
    block shifts every following block and marks them all as changed. That is an
    accepted trade-off for simplicity; a proper LCS diff would be the upgrade
    path.
    """
    highlighted_blocks = []
    for idx, new_block in enumerate(new_blocks):
        b_type = new_block.get("type")
        b_text = new_block.get("text")
        if idx < len(old_blocks):
            old_b = old_blocks[idx]
            if old_b.get("type") != b_type or old_b.get("text") != b_text:
                new_block["_highlight"] = True
        else:
            new_block["_highlight"] = True
        highlighted_blocks.append(new_block)
    return highlighted_blocks
