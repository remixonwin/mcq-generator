import json
from src.mcq_generator.utils import merge_mcqs


def make_mcq(source_document, question="Q"):
    return {
        "question": question,
        "options": ["A", "B", "C"],
        "correct_answer": 0,
        "explanation": "E",
        "metadata": {"source_document": source_document},
    }


def test_merge_overlapping_and_nonoverlapping():
    existing = {
        "generated_at": "2026-01-01T00:00:00",
        "dataset": "ds1",
        "total_questions": 3,
        "mcqs": [
            make_mcq("ds1_1", "old1"),
            make_mcq("ds1_2", "old2"),
            make_mcq("ds_other_x", "oldx"),
        ],
    }

    new = {
        "generated_at": "2026-01-02T00:00:00",
        "dataset": "ds1",
        "mcqs": [
            make_mcq("ds1_2", "new2"),  # overlaps existing
            make_mcq("ds1_3", "new3"),  # new keyed
            make_mcq(None, "no_key"),
        ],
    }

    merged = merge_mcqs(existing, new)

    # Expect merged to contain keys: ds1_1 (unchanged), ds1_2 (replaced), ds1_3 (appended),
    # plus existing other (ds_other_x) and new no-key.
    keys = [m.get("metadata", {}).get("source_document") for m in merged["mcqs"]]

    assert "ds1_1" in keys
    assert "ds1_2" in keys
    assert "ds1_3" in keys
    assert "ds_other_x" in keys

    # Verify that ds1_2 has the new content
    for m in merged["mcqs"]:
        if m.get("metadata", {}).get("source_document") == "ds1_2":
            assert m["question"] == "new2"


def test_ordering_stability():
    existing = {"mcqs": [make_mcq("a"), make_mcq("b"), make_mcq("c")]}
    new = {"mcqs": [make_mcq("b", "Bnew"), make_mcq("d", "Dnew")]}

    merged = merge_mcqs(existing, new)
    keys = [m.get("metadata", {}).get("source_document") for m in merged["mcqs"]]

    # existing order a,b,c should be preserved where possible, with b replaced, d appended
    assert keys[0] == "a"
    assert keys[1] == "b"
    assert "d" in keys
