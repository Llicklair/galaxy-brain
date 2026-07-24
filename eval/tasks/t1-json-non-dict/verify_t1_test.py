"""Arm-independent verifier for t1-json-non-dict (run with pytest, repo installed).

Contract under test: _extract_json_object's type hint promises dict. Valid-but-non-object
JSON must raise json.JSONDecodeError (which the driver reclassifies as a DriverError),
never flow through as list/str/None/int into judge_synthesis.
"""
import json

import pytest

from consejo.json_utils import _extract_json_object


@pytest.mark.parametrize("payload", ["[1,2,3]", '[{"plan": 1}]', '"texto"', "null", "42"])
def test_non_object_json_raises(payload):
    with pytest.raises(json.JSONDecodeError):
        _extract_json_object(payload)


def test_fenced_array_raises():
    with pytest.raises(json.JSONDecodeError):
        _extract_json_object("```json\n[1, 2, 3]\n```")


def test_object_still_parses():
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_fenced_object_still_parses():
    assert _extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
