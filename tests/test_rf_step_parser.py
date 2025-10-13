import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.test.performance import parse_rf_step_spec
from src.util.constants import DEFAULT_RF_STEP_SPEC


def test_parse_rf_step_spec_single_segment():
    assert parse_rf_step_spec("0,30:3") == list(range(0, 31, 3))


def test_parse_rf_step_spec_multiple_segments_deduplicate():
    assert parse_rf_step_spec("0,6:3;6,10:2") == [0, 3, 6, 8, 10]


def test_parse_rf_step_spec_old_two_value_format():
    assert parse_rf_step_spec([0, 3]) == [0, 1, 2]


def test_parse_rf_step_spec_invalid_fallback():
    assert parse_rf_step_spec("invalid") == parse_rf_step_spec(DEFAULT_RF_STEP_SPEC)


def test_parse_rf_step_spec_empty_uses_default():
    assert parse_rf_step_spec("") == parse_rf_step_spec(DEFAULT_RF_STEP_SPEC)
