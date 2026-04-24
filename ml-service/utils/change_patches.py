def apply_changes_by_span(text, changes, accepted_change_ids=None):
    """Apply anchored patches against the original text in descending order."""
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

    included_changes.sort(key=lambda item: (item[0], item[1]), reverse=True)

    updated_text = text
    for start, end, replacement_text in included_changes:
        updated_text = updated_text[:start] + replacement_text + updated_text[end:]

    return updated_text
