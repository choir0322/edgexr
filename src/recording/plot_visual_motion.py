"""Plot saved visual/gyro comparisons. Optional local Matplotlib dependency."""

from __future__ import annotations
from typing import Sequence


import argparse
import csv
import json
from pathlib import Path


def plot_comparisons(folders: Sequence[Path], output: Path) -> None:
    """Plot saved image-motion and gyro-Y comparisons on consistent per-row scales.

    Args:
        folders (Sequence[Path]): Existing comparison directories containing
            summary.json and motion.csv.
        output (Path): New destination path; existing output must be preserved.

    Returns:
        None: writes a new static chart and closes its figure; existing output is
            refused.
    """
    # Load the plotting library only for this command and use a noninteractive
    # backend suitable for an SSH terminal. Refuse to overwrite an existing plot.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if output.exists():
        raise ValueError("Output already exists; choose a new filename")

    # Allocate one column per run, with separate image-motion and gyro panels.
    # Read all pairs but draw motion traces only from accepted comparisons.
    figure, axes = plt.subplots(
        2, len(folders), figsize=(6 * len(folders), 6.8), squeeze=False, sharex=True
    )
    for column, folder in enumerate(folders):
        summary = json.loads((folder / "summary.json").read_text())
        with (folder / "motion.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        good = [r for r in rows if r["accepted"] == "True"]
        for row_index, key, color, label, bin_key in [
            (
                0,
                "horizontal_pixels_s",
                "#156b9a",
                "Image motion (pixels/s at 320×180)",
                "median_horizontal_pixels_s",
            ),
            (
                1,
                "gy_dps",
                "#bd5317",
                "Corrected gyro Y (degrees/s)",
                "median_gyro_y_dps",
            ),
        ]:
            # Overlay frame-pair values and one-second medians on each panel; the two
            # rows retain their distinct physical units rather than sharing a numerical scale.
            ax = axes[row_index, column]
            ax.plot(
                [float(r["host_after_cue_s"]) for r in good],
                [float(r[key]) for r in good],
                color=color,
                lw=0.65,
                alpha=0.5,
                label="Frame-pair estimate",
            )
            bins = [b for b in summary["per_second"] if b[bin_key] is not None]
            ax.plot(
                [b["second"] + 0.5 for b in bins],
                [b[bin_key] for b in bins],
                color=color,
                lw=2,
                label="1-second median",
            )

            # Mark zero, the initial bias window and rejected pair times so gaps and
            # calibration assumptions remain visible instead of being smoothed away.
            ax.axhline(0, color="#777777", lw=0.7)
            ax.axvspan(0, 1, color="#808080", alpha=0.12)
            for bad in rows:
                if bad["accepted"] != "True":
                    ax.axvline(
                        float(bad["host_after_cue_s"]),
                        color="#999999",
                        alpha=0.18,
                        lw=1,
                    )

            # Apply the existing 15-second display window and annotate run quality.
            # Low-variation recordings omit correlation instead of presenting a misleading r.
            ax.set_xlim(0, 15)
            ax.set_ylabel(label)
            ax.grid(alpha=0.15)
            ax.spines[["top", "right"]].set_visible(False)
            if row_index == 1:
                ax.set_xlabel("Seconds after cue (approximate host receipt timing)")
        correlation = summary["horizontal_vs_gyro_y_correlation"]
        text = (
            f"r = {correlation:.3f}"
            if correlation is not None
            else "correlation omitted: little motion"
        )
        axes[0, column].set_title(
            f"{summary['recording']}\n{summary['accepted_pairs']}/{summary['compared_pairs']} accepted pairs; {text}",
            fontsize=11,
        )

    # Use matching symmetric limits across runs for each physical quantity,
    # then label the timing limitations and save/close the completed figure.
    for row_index in (0, 1):
        limits = [ax.get_ylim() for ax in axes[row_index]]
        bound = max(max(abs(a), abs(b)) for a, b in limits)
        for ax in axes[row_index]:
            ax.set_ylim(-bound, bound)
    axes[0, 0].legend(loc="upper left", fontsize=8)
    figure.suptitle(
        "Image movement compared with corrected gyro readings", fontsize=15, y=0.99
    )
    figure.text(
        0.5,
        0.01,
        "Gray start: per-run bias window. Thin gray lines: rejected pairs. Opposite signs reflect image/sensor axes.\nNo fitted time shift, camera calibration, or exposure synchronization.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 0.94))
    figure.savefig(output, dpi=170)
    plt.close(figure)


def main() -> None:
    """Parse comparison folders and create the requested offline chart.

    Args:
        None.

    Returns:
        None: plotting/file errors propagate instead of being silently ignored.
    """
    # Parse existing analysis folders and the new figure filename, then render.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plot_comparisons(args.folders, args.output)


if __name__ == "__main__":
    main()
