"""Provider-specific adapters to normalize provider responses.

Each adapter should take a parsed JSON response and return a normalized
structure that contains a top-level 'choices' list where each choice is a
dict containing a 'message' key with a 'content' string. The ProviderClient
will call `adapt` before validating responses.
"""

from typing import Any, Dict, List


def _find_choices(obj: Any) -> List:
    """Recursively search an object for the first 'choices' list.

    Returns the list if found, otherwise an empty list.
    """
    if isinstance(obj, dict):
        if "choices" in obj and isinstance(obj["choices"], list):
            return obj["choices"]
        for v in obj.values():
            found = _find_choices(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_choices(item)
            if found:
                return found
    return []


def adapt(resp_json: Any, request_data: Dict | None = None) -> Any:
    """Attempt to adapt provider response shapes into the canonical form.

    This tries to be resilient to nested response wrappers (seen from Ollama,
    Litellm, etc.) by recursively searching for a 'choices' list and promoting
    it to the top-level shape expected by the generator.
    """
    # If it's already a dict with choices, return as-is
    if isinstance(resp_json, dict) and "choices" in resp_json:
        return resp_json

    # Provider hint: check request_data/model for known providers
    model_hint = ""
    try:
        if request_data and isinstance(request_data, dict):
            model_hint = str(request_data.get("model", "")).lower()
    except Exception:
        model_hint = ""

    # Recursively find choices anywhere in the payload
    choices = _find_choices(resp_json)
    if choices:
        # If this appears to be an Ollama response (model hint or embedded metadata),
        # normalize each choice to ensure a `message.content` field exists.
        if "ollama" in model_hint or "ollama" in str(resp_json).lower():
            normalized = []
            for ch in choices:
                content = ""
                if isinstance(ch, dict):
                    # Common Ollama shapes: {'message': {'content': ...}}, or
                    # {'text': '...'} or nested 'response' fields.
                    if "message" in ch and isinstance(ch["message"], dict):
                        content = ch["message"].get("content", "")
                    if not content and "text" in ch and isinstance(ch["text"], str):
                        content = ch["text"]
                    if not content and "content" in ch and isinstance(ch["content"], str):
                        content = ch["content"]
                    # Some Ollama variants nest final text under 'response'->'choices' etc.
                    if not content:
                        # try to stringify the whole choice as fallback
                        try:
                            import json as _json

                            content = _json.dumps(ch, ensure_ascii=False)
                        except Exception:
                            content = str(ch)
                else:
                    content = str(ch)

                normalized.append({"message": {"content": content}})

            return {"choices": normalized}

        # Generic promotion
        return {"choices": choices}

    # If top-level is a list of choices, promote
    if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
        return {"choices": resp_json}

    # Nothing recognized — return unchanged
    return resp_json
