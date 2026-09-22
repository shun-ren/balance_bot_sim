"""Metrics use SI internally. Unobserved recovery/settling is JSON null."""
import numpy as np


def settling_delay(times, good, start, end, minimum_hold=0.5):
    """First in-band sample that stays in band through the event window's end."""
    if end <= start:
        return None
    bad = np.flatnonzero(~good[start:end])
    index = start + int(bad[-1]) + 1 if len(bad) else start
    if index >= end or times[end-1] - times[index] < minimum_hold - 1e-9:
        return None
    return float(times[index] - times[start])


def compute(rows, config, reason):
    if not rows:
        return dict(status="no_data", termination_reason=reason, duration_s=0., samples=0)
    a = {key: np.array([row[key] for row in rows], dtype=float) for key in rows[0]}
    t, n = a["time"], len(rows)
    dt = float(a["dt"][0])
    angle_band, velocity_band = np.radians(2.), 0.1
    good = (np.abs(a["angle_error"]) <= angle_band) & (np.abs(a["velocity_error"]) <= velocity_band)
    # Event boundaries prevent a later push or command from invalidating an earlier response.
    command_changes = np.flatnonzero(np.abs(np.diff(a["desired_velocity"])) > 1e-9) + 1
    force_changes = np.flatnonzero(np.abs(np.diff(a["disturbance_force"])) > 1e-9) + 1
    push_starts = [int(i) for i in force_changes if a["disturbance_force"][i] != 0]
    if a["disturbance_force"][0] != 0:
        push_starts.insert(0, 0)
    disturbance_events = []
    for start in push_starts:
        following = [i for i in list(command_changes) + push_starts if i > start]
        end = min(following, default=n)
        off = start
        while off < end and a["disturbance_force"][off] != 0:
            off += 1
        deviation = np.append(a["angle"][start:end], a["end_angle"][end-1]) - a["angle"][start]
        sign = np.sign(a["disturbance_force"][start])
        recovery = settling_delay(t, good, off, end) if off < end else None
        disturbance_events.append(dict(time_s=float(t[start]), force_N=float(a["disturbance_force"][start]),
            peak_deviation_deg=float(np.degrees(np.max(np.abs(deviation)))),
            overshoot_deg=float(np.degrees(max(0., np.max(-sign * deviation)))),
            recovery_after_push_s=recovery,
            window_end_s=float(t[end-1] + dt)))
    tracking_events = []
    for start in command_changes:
        following = [i for i in list(command_changes) + push_starts if i > start]
        end = min(following, default=n)
        delay = settling_delay(t, np.abs(a["velocity_error"]) <= velocity_band, start, end)
        tracking_events.append(dict(time_s=float(t[start]), target_m_s=float(a["desired_velocity"][start]),
                                    settling_time_s=delay, window_end_s=float(t[end-1] + dt)))
    fell = bool(np.any(a["fell"]))
    tail = max(0, n - int(np.ceil(1 / dt)))
    stable = not fell and (t[-1]+dt >= 1) and bool(np.all(good[tail:]))
    return dict(status="fell" if fell else "stable" if stable else "unsettled",
        termination_reason=reason, duration_s=float(t[-1]+dt), samples=n,
        max_lean_deg=float(np.degrees(max(np.max(np.abs(a["angle"])), np.max(np.abs(a["end_angle"]))))),
        mean_abs_lean_deg=float(np.degrees(np.mean(np.abs(a["angle"])))),
        rms_angle_error_deg=float(np.degrees(np.sqrt(np.mean(a["angle_error"]**2)))),
        falls=int(fell), velocity_rmse_m_s=float(np.sqrt(np.mean(a["velocity_error"]**2))),
        peak_velocity_error_m_s=float(np.max(np.abs(a["velocity_error"]))),
        peak_torque_Nm=float(np.max(np.abs(a["actual_torque"]))),
        mean_abs_torque_Nm=float(np.mean(np.abs(a["actual_torque"]))),
        saturation_percent=float(100*np.mean(a["saturated"])),
        torque_squared_integral_Nm2_s=float(np.sum(a["actual_torque"]**2)*dt),
        peak_disturbance_N=float(np.max(np.abs(a["disturbance_force"]))),
        disturbance_events=disturbance_events, tracking_events=tracking_events,
        tolerances=dict(angle_deg=2., velocity_m_s=0.1, minimum_hold_s=0.5),
        largest_recoverable_disturbance_N=None,
        notes="Recovery/settling require remaining in band to the next event/end, for at least 0.5 s. "
              "Null means not observed or not measured. A single run cannot establish a recovery envelope.")
