"""Arm-independent verifier for t1-json-non-dict (run with pytest, repo installed).

Contract under test: _extract_json_object's type hint promises dict. Valid-but-non-object
JSON must raise json.JSONDecodeError (which the driver reclassifies as a DriverError),
never flow through as list/str/None/int into judge_synthesis.
"""
import json

import pytest

from consejo.json_utils import _extract_json_object


@pytest.mark.parametrize("payload", ["[1,2,3]", '"texto"', "null", "42"])
def test_pure_non_object_raises(payload):
    # No object anywhere in the payload: the only correct outcome is JSONDecodeError.
    with pytest.raises(json.JSONDecodeError):
        _extract_json_object(payload)


def test_fenced_array_raises():
    with pytest.raises(json.JSONDecodeError):
        _extract_json_object("```json\n[1, 2, 3]\n```")


def test_array_wrapping_object_never_returns_non_dict():
    # The TRUE contract: never return a non-dict. An agent may legitimately fix this
    # either by raising OR by unwrapping the embedded object (the brace-scan fallback) —
    # both prevent the judge crash. Only returning the raw list is a failure.
    try:
        result = _extract_json_object('[{"plan": 1}]')
    except json.JSONDecodeError:
        return
    assert isinstance(result, dict)


def test_object_still_parses():
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_fenced_object_still_parses():
    assert _extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
