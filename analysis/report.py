import json
import os
from pathlib import Path
import numpy as np
from .metrics import compute


def finish(logger, reason):
    logger.close()  # CSV is durable even if report generation fails.
    (logger.directory / "config.json").write_text(
        json.dumps(logger.metadata, indent=2), encoding="utf-8")
    result = compute(logger.rows, logger.metadata["config"], reason)
    result["scenario"] = logger.metadata["scenario"]
    summary_path = logger.directory / "summary.json"
    summary_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    if logger.rows:
        plot(logger.rows, result, logger.directory / "report.png")
    return result


def plot(rows, summary, path):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a = {key: np.array([r[key] for r in rows]) for key in rows[0]}
    with plt.rc_context({"figure.facecolor": "#101b29", "axes.facecolor": "#172638",
                         "text.color": "#e5edf7", "axes.labelcolor": "#b6c6d8",
                         "xtick.color": "#b6c6d8", "ytick.color": "#b6c6d8",
                         "axes.edgecolor": "#375069", "grid.color": "#375069",
                         "font.size": 10}):
        fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
        fig.subplots_adjust(top=.83, bottom=.07, hspace=.3)
        fig.text(.08, .95, "PLANAR / BALANCE LAB", fontsize=22, weight="bold")
        fig.text(.08, .916, f'{summary["scenario"].upper()}   /   {summary["status"].upper()}   /   '
                 f'{summary["duration_s"]:.2f} s   /   {summary["termination_reason"]}', fontsize=12, color="#56d9c0")
        fig.text(.08, .877, f'Peak lean {summary["max_lean_deg"]:.2f} deg     '
                 f'Angle RMS {summary["rms_angle_error_deg"]:.2f} deg     '
                 f'Velocity RMSE {summary["velocity_rmse_m_s"]:.3f} m/s     '
                 f'Saturation {summary["saturation_percent"]:.1f}%')
        series = [("angle", "desired_angle", "Lean (deg)", 180/np.pi),
                  ("velocity", "desired_velocity", "Velocity (m/s)", 1),
                  ("actual_torque", "commanded_torque", "Torque (Nm)", 1)]
        for ax, (actual, desired, label, scale) in zip(axes, series):
            ax.plot(a["time"], a[actual]*scale, color="#56d9c0", label=actual.replace("_", " "), lw=1.7)
            ax.plot(a["time"], a[desired]*scale, color="#f9bb69", label=desired.replace("_", " "), ls="--", lw=1.1)
            ax.set_ylabel(label)
            for event in summary["disturbance_events"]:
                ax.axvline(event["time_s"], color="#fc7184", alpha=.45, lw=.9)
        # Include the terminal state (especially the actual fall threshold crossing).
        axes[0].plot(a["time"][-1]+a["dt"][-1], np.degrees(a["end_angle"][-1]), ".", color="#56d9c0")
        axes[3].step(a["time"], a["disturbance_force"], where="post", color="#fc7184", label="external push")
        axes[3].set_ylabel("Force (N)")
        axes[3].set_xlabel("Simulation time (s)")
        for ax in axes:
            ax.grid(alpha=.4)
            ax.legend(loc="upper right", facecolor="#172638", edgecolor="#375069", labelcolor="#e5edf7")
        fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
        plt.close(fig)
