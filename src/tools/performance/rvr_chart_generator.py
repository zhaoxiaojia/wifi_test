"""Utilities to export RVR performance charts without the UI."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import List, Optional

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from src.util.constants import CHART_DPI, TEXT_COLOR
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
            placeholder = self._create_empty_chart(charts_dir, path.stem or "RVR Chart", [])
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
                image = self._save_pie_chart(group, title, charts_dir)
            else:
                image = self._save_line_chart(group, title, charts_dir)
            if image is not None:
                results.append(image)
        if not results:
            placeholder = self._create_empty_chart(charts_dir, path.stem or "RVR Chart", [])
            if placeholder is not None:
                results.append(placeholder)
        return results

    # --- helpers to render matplotlib charts ---
    def _save_line_chart(self, group: pd.DataFrame, title: str, charts_dir: Path) -> Optional[Path]:
        steps = self._collect_step_labels(group)
        if not steps:
            return self._create_empty_chart(charts_dir, title, [])
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
                return self._create_empty_chart(charts_dir, title, steps)
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

    def _save_pie_chart(self, group: pd.DataFrame, title: str, charts_dir: Path) -> Optional[Path]:
        channel_values: list[tuple[str, float]] = []
        for channel, channel_df in group.groupby("__channel_display__", dropna=False):
            throughput_values = [
                float(v)
                for v in channel_df["__throughput_value__"].tolist()
                if isinstance(v, (int, float))
                and pd.notna(v)
                and math.isfinite(float(v))
            ]
            if not throughput_values:
                continue
            avg_value = sum(throughput_values) / len(throughput_values)
            label = self._format_pie_channel_label(channel, channel_df)
            channel_values.append((label, avg_value))
        if not channel_values:
            return self._create_empty_chart(charts_dir, title, [])
        labels, values = zip(*channel_values)
        fig, ax = plt.subplots(figsize=(6.2, 6.2), dpi=CHART_DPI)
        try:
            autopct = self._make_pie_autopct(values)
            wedges, _, autotexts = ax.pie(
                values,
                startangle=120,
                autopct=autopct,
                pctdistance=0.7,
                textprops={"color": TEXT_COLOR},
            )
            ax.set_title(title, pad=6)
            ax.axis("equal")
            legend_handles = list(wedges)
            legend_labels = list(labels)
            annotations = self._collect_user_annotations(group)
            if annotations:
                legend_handles.extend([Line2D([], [], linestyle="None", marker="", linewidth=0) for _ in annotations])
                legend_labels.extend(annotations)
            legend = ax.legend(
                legend_handles,
                legend_labels,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
            )
            if legend is not None:
                for text_item in legend.get_texts():
                    text_item.set_ha("left")
            for autotext in autotexts:
                autotext.set_color(TEXT_COLOR)
            fig.tight_layout(pad=0.6)
            save_path = charts_dir / f"{self._safe_chart_name(title)}.png"
            fig.savefig(save_path, dpi=fig.dpi)
            return save_path
        except Exception:
            logging.exception("Failed to save RVR pie chart: %s", title)
            return None
        finally:
            plt.close(fig)

    def _create_empty_chart(self, charts_dir: Path, title: str, steps: List[str]) -> Optional[Path]:
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
