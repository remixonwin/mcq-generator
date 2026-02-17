from datetime import datetime
from typing import Dict, List, Any


def merge_mcqs(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two mcqs JSON-like dictionaries (with keys: generated_at, dataset, total_questions, mcqs).

    Strategy:
    - Use metadata.source_document as the canonical key when present.
    - Preserve the order of existing mcqs; for existing entries replaced by new ones, keep the original position.
    - Append any new mcqs that don't match existing keys at the end, preserving new order.
    - Keep entries without source_document at the end; existing ones first, then new ones.
    """
    existing_mcqs: List[Dict[str, Any]] = existing.get("mcqs", []) if existing else []
    new_mcqs: List[Dict[str, Any]] = new.get("mcqs", []) if new else []

    # Prefer job_id as canonical key when present, fall back to source_document
    def key_of(m: Dict[str, Any]) -> str | None:
        md = m.get("metadata", {})
        if not isinstance(md, dict):
            return None
        if md.get("job_id"):
            return f"job:{md.get('job_id')}:idx:{md.get('document_index') or md.get('source_document')}"
        if md.get("source_document"):
            return md.get("source_document")
        return None

    existing_map = {}
    existing_order = []
    existing_others = []
    for m in existing_mcqs:
        k = key_of(m)
        if k:
            existing_map[k] = m
            existing_order.append(k)
        else:
            existing_others.append(m)

    new_map = {}
    new_order = []
    new_others = []
    for m in new_mcqs:
        k = key_of(m)
        if k:
            new_map[k] = m
            new_order.append(k)
        else:
            new_others.append(m)

    # Merge: start with existing order, replacing with new when present
    merged_list = []
    seen = set()
    for key in existing_order:
        if key in new_map:
            merged_list.append(new_map[key])
            seen.add(key)
        else:
            merged_list.append(existing_map[key])
            seen.add(key)

    # Append any new keyed entries that weren't in existing
    for key in new_order:
        if key not in seen:
            merged_list.append(new_map[key])
            seen.add(key)

    # Append others: existing others first, then new others
    merged_list.extend(existing_others)
    merged_list.extend(new_others)

    out = {
        "generated_at": datetime.now().isoformat(),
        "dataset": new.get("dataset") or existing.get("dataset"),
        "total_questions": len(merged_list),
        "mcqs": merged_list,
    }

    return out
