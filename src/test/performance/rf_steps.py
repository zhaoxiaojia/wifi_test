"""RF step parsing helpers shared across performance tests."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from src.util.constants import DEFAULT_RF_STEP_SPEC, RF_STEP_SPLIT_PATTERN


def parse_optional_int(
    value: Any,
    *,
    field_name: str = "value",
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> Optional[int]:
    """Safely coerce assorted config values to ints, clamping to bounds."""
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    if isinstance(value, (list, tuple, set)):
        for item in value:
            parsed = parse_optional_int(item, field_name=field_name, min_value=min_value, max_value=max_value)
            if parsed is not None:
                return parsed
        return None

    if value is None:
        return None

    try:
        number = int(float(value))
    except (TypeError, ValueError):
        logging.warning("Invalid %s: %r", field_name, value)
        return None

    if min_value is not None and number < min_value:
        logging.warning("%s %s lower than minimum %s, clamped.", field_name, number, min_value)
        number = min_value
    if max_value is not None and number > max_value:
        logging.warning("%s %s higher than maximum %s, clamped.", field_name, number, max_value)
        number = max_value
    return number


def _is_scalar(value: Any) -> bool:
    return not isinstance(value, (list, tuple, set, dict))


def collect_rf_step_segments(raw_step: Any) -> list[str]:
    """Normalize arbitrary rf_solution.step inputs into string segments."""
    segments: list[str] = []

    def _collect(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return
            normalized = text.replace("；", ";").replace("，", ",").replace("。", ".").replace("：", ":")
            for part in RF_STEP_SPLIT_PATTERN.split(normalized):
                part = part.strip()
                if part:
                    segments.append(part)
            return
        if isinstance(value, (list, tuple, set)):
            items = list(value)
            if len(items) == 2 and all(_is_scalar(i) for i in items):
                start = str(items[0]).strip()
                stop = str(items[1]).strip()
                if start and stop:
                    segments.append(f"{start},{stop}")
                return
            for item in items:
                _collect(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                _collect(item)
            return
        text = str(value).strip()
        if text:
            segments.append(text)

    _collect(raw_step)
    return segments


@dataclass(frozen=True)
class StepSegment:
    """Normalized numeric segment derived from rf_solution.step."""

    start: int
    stop: int
    step: int = 1
    explicit_step: bool = False

    def iter_values(self) -> Iterable[int]:
        """Yield discrete attenuation values represented by this segment."""
        exclusive_stop = not self.explicit_step and self.start != self.stop
        current = self.start
        stop = self.stop
        while current <= stop:
            if exclusive_stop and current == stop:
                break
            yield current
            current += self.step


def _parse_segment(segment: str) -> StepSegment | None:
    normalized = segment.strip()
    if not normalized:
        return None
    normalized = normalized.replace("；", ";").replace("，", ",").replace("：", ":")
    explicit_step = ":" in normalized
    if explicit_step:
        range_part, step_part = normalized.split(":", 1)
    else:
        range_part, step_part = normalized, None

    tokens = [tok for tok in re.split(r"[\s,]+", range_part.strip()) if tok]
    if not tokens:
        logging.warning("Empty rf_solution.step segment ignored: %r", segment)
        return None
    if len(tokens) > 2:
        logging.warning("rf_solution.step segment %r has too many bounds, only the first two values are used.", segment)

    start_token = tokens[0]
    stop_token = tokens[1] if len(tokens) >= 2 else tokens[0]

    start = parse_optional_int(start_token, field_name="rf_solution.step.start")
    stop = parse_optional_int(stop_token, field_name="rf_solution.step.stop")

    if start is None:
        return None
    if stop is None:
        stop = start
    if stop < start:
        logging.warning("rf_solution.step stop %s lower than start %s, swapping.", stop, start)
        start, stop = stop, start

    if step_part is not None:
        step_value = parse_optional_int(step_part, field_name="rf_solution.step.step", min_value=1)
        step = step_value if step_value is not None else 1
    else:
        step = 1

    if step <= 0:
        logging.warning("rf_solution.step step %s <= 0, fallback to 1", step)
        step = 1

    return StepSegment(start=start, stop=stop, step=step, explicit_step=explicit_step)


def expand_rf_step_segments(segment_specs: list[str]) -> list[int]:
    """Expand normalized segment strings into sorted unique attenuation values."""
    values: list[int] = []
    seen: set[int] = set()
    for spec in segment_specs:
        segment = _parse_segment(spec)
        if segment is None:
            continue
        for value in segment.iter_values():
            if value not in seen:
                values.append(value)
                seen.add(value)
    return values


def parse_rf_step_spec(raw_step: Any) -> list[int]:
    """Return the expanded RF step list, falling back to the default spec."""
    segments = collect_rf_step_segments(raw_step)
    values = expand_rf_step_segments(segments)
    if values:
        return values
    if raw_step not in (None, "", DEFAULT_RF_STEP_SPEC):
        logging.warning("rf_solution.step is empty or invalid (%r), fallback to default %s", raw_step, DEFAULT_RF_STEP_SPEC)
    default_segments = collect_rf_step_segments(DEFAULT_RF_STEP_SPEC)
    default_values = expand_rf_step_segments(default_segments)
    return default_values if default_values else [0]


def parse_turntable_step_bounds(raw_step: Any) -> tuple[int, int] | None:
    """Parse turntable bounds as a tuple (start, stop) if possible."""
    if raw_step is None:
        return None
    if isinstance(raw_step, str):
        tokens = [segment.strip() for segment in re.split(r"[,，]", raw_step) if segment.strip()]
    elif isinstance(raw_step, (list, tuple, set)):
        tokens = [str(item).strip() for item in raw_step if str(item).strip()]
    else:
        tokens = [str(raw_step).strip()]

    values: list[int] = []
    for token in tokens:
        if not token:
            continue
        try:
            values.append(int(token))
        except (TypeError, ValueError):
            logging.warning("Invalid turntable step token %r ignored", token)
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        return values[0], values[0]
    return None
