"""Helper functions for response validation."""

import json


def validate_response(text):
    """Check if a response looks like a valid Google Maps API response.

    Returns (is_valid, error_message)
    """
    if not text:
        return False, "Empty response"

    if text.startswith(")]}'"):
        text = text[4:].strip()

    if text.startswith("{"):
        try:
            data = json.loads(text)
            if "d" in data:
                return True, None
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

    if text.startswith("["):
        try:
            json.loads(text)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON array: {e}"

    return False, f"Unexpected response format: {text[:50]}"
