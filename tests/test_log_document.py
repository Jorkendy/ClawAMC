import airtable_client as ac


def test_next_version_empty():
    assert ac._next_doc_version([], "Brief") == 1


def test_next_version_counts_same_loai():
    rows = [
        {"fields": {"Loại": "Brief"}},
        {"fields": {"Loại": "Proposal"}},
        {"fields": {"Loại": "Brief"}},
    ]
    assert ac._next_doc_version(rows, "Brief") == 3
    assert ac._next_doc_version(rows, "Proposal") == 2
    assert ac._next_doc_version(rows, "Plan") == 1
