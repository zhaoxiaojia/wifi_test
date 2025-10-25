#!/usr/bin/env python
# encoding: utf-8
"""
Utilities to interact with the RF and turntable controllers used in RVR tests.
"""

import logging
import re
import subprocess
from typing import Optional

from src.util.decorators import singleton


@singleton
class rs:
    def __init__(self):
        self.rf_path = 'res/AmlACUControl.exe'
        self.corner_path = 'res/AmlSunveyController.exe'
        self.rf: int = 0
        self.current_angle: str = ''
        self.current_angle_value: Optional[float] = None
        self.current_distance: str = ''

    @staticmethod
    def _extract_final_numeric(text: str) -> Optional[float]:
        if not text:
            return None
        matches = re.findall(r'-?\d+(?:\.\d+)?', text)
        if not matches:
            return None
        try:
            return float(matches[-1])
        except ValueError:
            return None

    def execute_rf_cmd(self, num: int) -> None:
        exe_path = f'{self.rf_path} {num}'
        subprocess.run(exe_path, capture_output=True, text=True)
        self.rf = num

    def get_rf_current_value(self) -> int:
        return self.rf

    def get_turntanle_current_angle(self) -> str:
        return self.current_angle

    def set_turntable_zero(self) -> None:
        self.execute_turntable_cmd('', 0)

    def execute_turntable_cmd(self, type, angle='') -> None:
        # invoke the AutoIt-compiled executable to drive the turntable
        exe_path = f"{self.corner_path} -angle {angle}"
        result = subprocess.run(exe_path, capture_output=True, text=True)

        raw_output = result.stdout or ""
        output = raw_output.strip()
        cleaned = output.replace('\r\n', '\n')

        angle_segment = cleaned
        distance_segment = ''
        if '|' in cleaned:
            angle_segment, distance_segment = cleaned.split('|', 1)
            angle_segment = angle_segment.strip()
            distance_segment = distance_segment.strip()

        lines = [line.strip() for line in angle_segment.split('\n') if line.strip()]
        joined_angle_text = '\n'.join(lines) if lines else angle_segment
        numeric_angle = self._extract_final_numeric(joined_angle_text)
        if numeric_angle is None and distance_segment:
            numeric_angle = self._extract_final_numeric(cleaned)

        if numeric_angle is not None:
            normalized_angle = numeric_angle % 360.0
            if normalized_angle < 0:
                normalized_angle += 360.0
            rounded = round(normalized_angle)
            if abs(normalized_angle - rounded) < 1e-6:
                display_angle = f"{int(rounded)}°"
            else:
                display_angle = f"{normalized_angle:.1f}°"
            self.current_angle_value = normalized_angle
            self.current_angle = display_angle
            logging.info("Current Angle: %s", display_angle)
        else:
            self.current_angle_value = None
            self.current_angle = joined_angle_text
            logging.info("Current Angle (raw): %s", joined_angle_text)

        distance_value = self._extract_final_numeric(distance_segment)
        if distance_value is not None:
            self.current_distance = f"{distance_value}"
        else:
            self.current_distance = distance_segment
        if distance_segment:
            logging.info("Current Distance: %s", self.current_distance)
        elif distance_segment == '':
            logging.debug("Turntable distance not reported in output: %s", output)
