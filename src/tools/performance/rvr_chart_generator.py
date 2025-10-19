"""Utilities to export RVR performance charts without the UI."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import List, Optional

import math

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from src.util.constants import CHART_DPI
from src.util.rvr_chart_logic import RvrChartLogic


class PerformanceRvrChartGenerator(RvrChartLogic):
    """Generate RVR/RVO summary charts for performance test results."""

    def generate(self, path: Path) -> List[Path]:
        """Build charts for *path* and return the saved image paths."""
        path = path.resolve()
        if not path.exists():
            logging.warning("RVR result file not found: %s", path)
            return []
        df = self._load_rvr_dataframe(path)
        charts_dir = path.parent / "rvr_charts"
        charts_dir.mkdir(exist_ok=True)
        if df.empty:
            inferred = self._infer_test_type_from_path(path)
            chart_kind = "polar" if inferred and inferred.strip().upper() == "RVO" else "line"
            placeholder = self._create_empty_chart(
                charts_dir,
                path.stem or "RVR Chart",
                [],
                chart_type=chart_kind,
            )
            return [placeholder] if placeholder is not None else []
        results: List[Path] = []
        grouped = df.groupby(
            [
                "__standard_display__",
                "__bandwidth_display__",
                "__freq_band_display__",
                "__test_type_display__",
                "__direction_display__",
            ],
            dropna=False,
        )
        sorted_groups = sorted(grouped, key=lambda item: self._group_sort_key(item[0]))
        for (standard, bandwidth, freq_band, test_type, direction), group in sorted_groups:
            if not direction:
                continue
            title = self._format_chart_title(standard, bandwidth, freq_band, test_type, direction)
            if not title:
                continue
            normalized_type = (test_type or "").strip().upper()
            if normalized_type == "RVO":
                image = self._save_rvo_chart(group, title, charts_dir)
            else:
                image = self._save_line_chart(group, title, charts_dir)
            if image is not None:
                results.append(image)
        if not results:
            inferred = self._infer_test_type_from_path(path)
            chart_kind = "polar" if inferred and inferred.strip().upper() == "RVO" else "line"
            placeholder = self._create_empty_chart(
                charts_dir,
                path.stem or "RVR Chart",
                [],
                chart_type=chart_kind,
            )
            if placeholder is not None:
                results.append(placeholder)
        return results

    # --- helpers to render matplotlib charts ---
    def _save_line_chart(self, group: pd.DataFrame, title: str, charts_dir: Path) -> Optional[Path]:
        steps = self._collect_step_labels(group)
        if not steps:
            return self._create_empty_chart(charts_dir, title, [], chart_type="line")
        x_positions = list(range(len(steps)))
        has_series = False
        fig, ax = plt.subplots(figsize=(7.8, 4.4), dpi=CHART_DPI)
        all_values: list[float] = []
        try:
            for channel, channel_df in group.groupby("__channel_display__", dropna=False):
                channel_name = channel or "Unknown"
                values: list[Optional[float]] = []
                for step in steps:
                    subset = channel_df[channel_df["__step__"] == step]
                    raw_values = [v for v in subset["__throughput_value__"].tolist() if v is not None]
                    finite_values = [
                        float(v)
                        for v in raw_values
                        if isinstance(v, (int, float))
                    ]
                    finite_values = [v for v in finite_values if pd.notna(v)]
                    if finite_values:
                        avg_value = sum(finite_values) / len(finite_values)
                        values.append(avg_value)
                        all_values.append(avg_value)
                    else:
                        values.append(None)
                if any(v is not None for v in values):
                    has_series = True
                    ax.plot(
                        x_positions,
                        self._series_with_nan(values),
                        marker="o",
                        label=self._format_channel_series_label(channel_name),
                    )
            if not has_series:
                return self._create_empty_chart(charts_dir, title, steps, chart_type="line")
            self._configure_step_axis(ax, steps)
            ax.set_xlabel("attenuation (dB)")
            ax.set_ylabel("throughput (Mbps)")
            ax.set_title(title, loc="left", pad=4)
            ax.grid(alpha=0.3, linestyle="--")
            if all_values:
                y_max = max(all_values)
                y_min = min(all_values)
                span = max(y_max - y_min, 1.0)
                extra = max(span * 0.15, y_max * 0.05, 1.0)
                ax.set_ylim(bottom=0, top=y_max + extra)
            else:
                ax.set_ylim(bottom=0)
            handles, labels = ax.get_legend_handles_labels()
            handles = list(handles)
            labels = list(labels)
            if handles:
                annotations = self._collect_user_annotations(group)
                if annotations:
                    dummy_handles = [Line2D([], [], linestyle="None", marker="", linewidth=0) for _ in annotations]
                    handles.extend(dummy_handles)
                    labels.extend(annotations)
                column_count = max(1, min(len(handles), 4))
                legend = ax.legend(
                    handles,
                    labels,
                    loc="lower center",
                    bbox_to_anchor=(0.5, 0.02),
                    ncol=column_count,
                    borderaxespad=0.2,
                    frameon=False,
                )
                if legend is not None:
                    for text_item in legend.get_texts():
                        text_item.set_ha("center")
            fig.tight_layout(pad=0.6)
            save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
            fig.savefig(save_path, dpi=fig.dpi)
            return save_path
        except Exception:
            logging.exception("Failed to save RVR line chart: %s", title)
            return None
        finally:
            plt.close(fig)

    def _save_rvo_chart(self, group: pd.DataFrame, title: str, charts_dir: Path) -> Optional[Path]:
        angle_positions = self._collect_angle_positions(group)
        if not angle_positions:
            return self._create_empty_chart(charts_dir, title, [], chart_type="polar")
        angle_values = [value for value, _ in angle_positions]
        angle_labels = [label for _, label in angle_positions]
        theta = [math.radians(value) for value in angle_values]
        theta_cycle = theta + [theta[0]] if theta else []
        fig, ax = plt.subplots(figsize=(6.6, 6.6), dpi=CHART_DPI, subplot_kw={"projection": "polar"})
        try:
            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)
            ax.set_xticks(theta)
            ax.set_xticklabels(angle_labels)
            channel_series = self._collect_rvo_channel_series(group, angle_values)
            if not channel_series:
                return self._create_empty_chart(charts_dir, title, [], chart_type="polar")
            all_values: list[float] = []
            for series_label, values in channel_series:
                cycle_values = list(values)
                cycle_values.append(values[0] if values else None)
                ax.plot(theta_cycle, self._series_with_nan(cycle_values), marker="o", label=series_label)
                all_values.extend([v for v in values if v is not None])
            if all_values:
                max_value = max(all_values)
                if max_value <= 0:
                    max_value = 1.0
                extra = max(max_value * 0.15, 1.0)
                ax.set_ylim(0, max_value + extra)
            else:
                ax.set_ylim(0, 1)
            ax.set_rlabel_position(135)
            ax.grid(alpha=0.3, linestyle="--")
            ax.set_title(title, pad=8)
            handles, labels = ax.get_legend_handles_labels()
            handles = list(handles)
            labels = list(labels)
            legend = None
            print(f"[RVO] legend handles={labels}")
            bottom_padding = 0.22
            if handles:
                print(
                    f"[RVO] attempting to create legend -> handle_count={len(handles)}, label_count={len(labels)}"
                )
                legend = ax.legend(
                    handles,
                    labels,
                    loc="lower center",
                    bbox_to_anchor=(0.5, -0.08),
                    ncol=max(1, min(len(handles), 3)),
                    frameon=False,
                )
                legend_texts = [text.get_text() for text in legend.get_texts()] if legend else []
                print(
                    f"[RVO] legend created -> present={legend is not None}, texts={legend_texts}"
                )
                if legend is not None:
                    for text_item in legend.get_texts():
                        text_item.set_ha("center")
                bottom_padding = max(bottom_padding, 0.26)
            else:
                print("[RVO] legend skipped -> no handles detected")
            print(
                f"[RVO] subplot padding configuration -> bottom={bottom_padding}, legend_present={bool(ax.get_legend())}"
            )
            fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=bottom_padding)
            save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
            fig.savefig(save_path, dpi=fig.dpi)
            return save_path
        except Exception:
            logging.exception("Failed to save RVO chart: %s", title)
            return None
        finally:
            plt.close(fig)

    def _create_empty_chart(
        self, charts_dir: Path, title: str, steps: List[str], chart_type: str = "line"
    ) -> Optional[Path]:
        chart_type = (chart_type or "line").lower()
        if chart_type == "polar":
            fig = plt.figure(figsize=(6.6, 6.6), dpi=CHART_DPI)
            try:
                ax = fig.add_subplot(111, projection="polar")
                ax.set_theta_zero_location("N")
                ax.set_theta_direction(-1)
                ax.set_xticks([])
                ax.set_yticks([])
                ax.set_ylim(0, 1)
                ax.grid(alpha=0.25, linestyle="--")
                ax.set_title(title, pad=8)
                ax.text(0.5, 0.5, "No data collected yet", transform=ax.transAxes, ha="center", va="center", color="#888888")
                fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.2)
                save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
                fig.savefig(save_path, dpi=fig.dpi)
                return save_path
            except Exception:
                logging.exception("Failed to save polar placeholder chart: %s", title)
                return None
            finally:
                plt.close(fig)

        fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=CHART_DPI)
        try:
            if steps:
                self._configure_step_axis(ax, steps)
            else:
                ax.set_xticks([])
                ax.set_xlim(0, 1)
            ax.set_xlabel("attenuation (dB)")
            ax.set_ylabel("throughput (Mbps)")
            ax.set_title(title, loc="left", pad=4)
            ax.grid(alpha=0.2, linestyle="--")
            ax.set_ylim(0, 1)
            ax.text(0.5, 0.5, "No data collected yet", transform=ax.transAxes, ha="center", va="center", color="#888888")
            fig.tight_layout(pad=0.6)
            save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
            fig.savefig(save_path, dpi=fig.dpi)
            return save_path
        except Exception:
            logging.exception("Failed to save placeholder chart: %s", title)
            return None
        finally:
            plt.close(fig)


def generate_rvr_charts(result_file: Path | str) -> List[Path]:
    """Convenience wrapper to build charts for *result_file*."""
    generator = PerformanceRvrChartGenerator()
    return generator.generate(Path(result_file))
