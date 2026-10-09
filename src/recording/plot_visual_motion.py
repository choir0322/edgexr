"""Plot saved visual/gyro comparisons. Optional local Matplotlib dependency."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Sequence


# Parse and validate explicit command-line options.
import argparse

# Read/write explicit numeric columns for reproducible offline analysis.
import csv

# Read or serialize metadata and browser/report payloads.
import json

# Work with explicit filesystem paths rather than shell expansions.
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
    # Load the optional plotting runtime only for the chart command.
    import matplotlib

    # Call matplotlib.use for this step; its contract describes the result or side effect.
    matplotlib.use("Agg")
    # Build the requested offline comparison figure.
    import matplotlib.pyplot as plt

    # Reject this invalid input before it can produce misleading output.
    if output.exists():
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Output already exists; choose a new filename")
    # Prepare figure, axes for the next step using the values calculated so far.
    figure, axes = plt.subplots(
        2, len(folders), figsize=(6 * len(folders), 6.8), squeeze=False, sharex=True
    )
    # Process each (column, folder) in the selected collection.
    for column, folder in enumerate(folders):
        # Package measurements with settings and limitations for reproducible interpretation.
        summary = json.loads((folder / "summary.json").read_text())
        # Keep these resources scoped so they are released even if the operation fails.
        with (folder / "motion.csv").open() as handle:
            # Prepare/read the detailed rows that will be validated or summarized next.
            rows = list(csv.DictReader(handle))
        # Prepare good for the next step using the values calculated so far.
        good = [r for r in rows if r["accepted"] == "True"]
        # Process each (row_index, key, color, label, bin_key) in the selected collection.
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
            # Prepare ax for the next step using the values calculated so far.
            ax = axes[row_index, column]
            # Call ax.plot for this step; its contract describes the result or side effect.
            ax.plot(
                [float(r["host_after_cue_s"]) for r in good],
                [float(r[key]) for r in good],
                color=color,
                lw=0.65,
                alpha=0.5,
                label="Frame-pair estimate",
            )
            # Prepare one-second summaries for easier visual/gyro comparison.
            bins = [b for b in summary["per_second"] if b[bin_key] is not None]
            # Call ax.plot for this step; its contract describes the result or side effect.
            ax.plot(
                [b["second"] + 0.5 for b in bins],
                [b[bin_key] for b in bins],
                color=color,
                lw=2,
                label="1-second median",
            )
            # Call ax.axhline for this step; its contract describes the result or side effect.
            ax.axhline(0, color="#777777", lw=0.7)
            # Call ax.axvspan for this step; its contract describes the result or side effect.
            ax.axvspan(0, 1, color="#808080", alpha=0.12)
            # Process each bad in the selected collection.
            for bad in rows:
                # Choose the next branch using bad['accepted'] != 'True'.
                if bad["accepted"] != "True":
                    # Call ax.axvline for this step; its contract describes the result or side
                    # effect.
                    ax.axvline(
                        float(bad["host_after_cue_s"]),
                        color="#999999",
                        alpha=0.18,
                        lw=1,
                    )
            # Call ax.set_xlim for this step; its contract describes the result or side effect.
            ax.set_xlim(0, 15)
            # Call ax.set_ylabel for this step; its contract describes the result or side
            # effect.
            ax.set_ylabel(label)
            # Call ax.grid for this step; its contract describes the result or side effect.
            ax.grid(alpha=0.15)
            # Call ax.spines[['top', 'right']].set_visible for this step; its contract describes
            # the result or side effect.
            ax.spines[["top", "right"]].set_visible(False)
            # Choose the next branch using row_index == 1.
            if row_index == 1:
                # Call ax.set_xlabel for this step; its contract describes the result or side
                # effect.
                ax.set_xlabel("Seconds after cue (approximate host receipt timing)")
        # Avoid reporting a correlation when either signal has almost no variation.
        correlation = summary["horizontal_vs_gyro_y_correlation"]
        # Prepare text for the next step using the values calculated so far.
        text = (
            f"r = {correlation:.3f}"
            if correlation is not None
            else "correlation omitted: little motion"
        )
        # Call axes[0, column].set_title for this step; its contract describes the result or
        # side effect.
        axes[0, column].set_title(
            f"{summary['recording']}\n{summary['accepted_pairs']}/{summary['compared_pairs']} accepted pairs; {text}",
            fontsize=11,
        )
    # Consistent scales make the stationary control directly comparable.
    for row_index in (0, 1):
        # Prepare limits for the next step using the values calculated so far.
        limits = [ax.get_ylim() for ax in axes[row_index]]
        # Prepare bound for the next step using the values calculated so far.
        bound = max(max(abs(a), abs(b)) for a, b in limits)
        # Process each ax in the selected collection.
        for ax in axes[row_index]:
            # Call ax.set_ylim for this step; its contract describes the result or side effect.
            ax.set_ylim(-bound, bound)
    # Call axes[0, 0].legend for this step; its contract describes the result or side effect.
    axes[0, 0].legend(loc="upper left", fontsize=8)
    # Call figure.suptitle for this step; its contract describes the result or side effect.
    figure.suptitle(
        "Image movement compared with corrected gyro readings", fontsize=15, y=0.99
    )
    # Call figure.text for this step; its contract describes the result or side effect.
    figure.text(
        0.5,
        0.01,
        "Gray start: per-run bias window. Thin gray lines: rejected pairs. Opposite signs reflect image/sensor axes.\nNo fitted time shift, camera calibration, or exposure synchronization.",
        ha="center",
        fontsize=9,
    )
    # Call figure.tight_layout for this step; its contract describes the result or side effect.
    figure.tight_layout(rect=(0, 0.07, 1, 0.94))
    # Call figure.savefig for this step; its contract describes the result or side effect.
    figure.savefig(output, dpi=170)
    # Release the stream or server resource after use.
    plt.close(figure)


def main() -> None:
    """Parse comparison folders and create the requested offline chart.

    Args:
        None.

    Returns:
        None: plotting/file errors propagate instead of being silently ignored.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare folders with its existing default, validation and help text.
    parser.add_argument("folders", nargs="+", type=Path)
    # Declare --output with its existing default, validation and help text.
    parser.add_argument("--output", required=True, type=Path)
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args()
    # Call plot_comparisons for this step; its contract describes the result or side effect.
    plot_comparisons(args.folders, args.output)


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call main for this step; its contract describes the result or side effect.
    main()
