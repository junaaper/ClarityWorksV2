def apply_changes_by_span(text, changes, accepted_change_ids=None):
    """Apply anchored patches against the original text using forward-offset tracking."""
    accepted_ids = set(accepted_change_ids) if accepted_change_ids is not None else None
    included_changes = []

    for change in changes or []:
        change_id = change.get('id')
        if accepted_ids is not None and change_id not in accepted_ids:
            continue

        start = int(change.get('start', change.get('position', 0)) or 0)
        end = int(change.get('end', start) or start)
        replacement_text = change.get('replacement_text')
        if replacement_text is None:
            replacement_text = change.get('simplified', '')

        start = max(0, min(len(text), start))
        end = max(start, min(len(text), end))
        included_changes.append((start, end, replacement_text))

    included_changes.sort(key=lambda item: (item[0], item[1]))

    filtered = []
    prev_end = -1
    for start, end, replacement in included_changes:
        if start < prev_end:
            continue
        filtered.append((start, end, replacement))
        prev_end = end

    result = []
    last_end = 0
    for start, end, replacement in filtered:
        result.append(text[last_end:start])
        result.append(replacement)
        last_end = end
    result.append(text[last_end:])

    return ''.join(result)
