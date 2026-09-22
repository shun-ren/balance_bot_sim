# Planar / Balance Lab

A Python simulator for studying balance, disturbance rejection and velocity tracking with cascaded PID control. Built from the *Planar Humanoid Balance & Control Simulator* handover. The user commands velocity; the controllers produce lean and torque requests; the plant integrates the resulting motion.

![Interactive simulator](runs/interface.png)

## Launch on this computer

**Double-click `launch.bat`. Press Enter to start an experiment.**

The project-local Python runtime and dependencies are already installed in `.runtime/`. The pre-existing `venv/` pointed to a missing Python 3.12 installation and was left untouched. The launcher prefers the working local runtime and does not require activating an environment.

From PowerShell in this folder:

```powershell
.\launch.bat
.\launch.bat --preset tracking
.\launch.bat --suite
```

On a fresh Windows x64 checkout, run `powershell -ExecutionPolicy Bypass -File .\setup.ps1` once. It downloads official CPython 3.12.10 embeddable Python and installs the verified dependencies locally, then use `launch.bat`. No administrator access or system Python changes are needed. Internet access is required for setup. `.runtime/` is intentionally excluded from Git.

Alternatively, with a normal Python 3.10+ installation (Windows/macOS/Linux):

```text
python -m venv .venv
# Activate .venv using the command appropriate for your shell.
python -m pip install -r requirements.txt
python main.py
```

`requirements.txt` gives compatible ranges for a fresh environment; `requirements-lock.txt` records the exact Windows/Python 3.12 verification environment.

## Interactive experiments

The setup screen lets you select a preset and change gains, physics, timing and push settings before every run. Hover over any parameter to see what it controls and how raising or lowering it affects balance. A run ends on a fall, its configured duration (20 s by default), Escape, reset or window close. Completed runs open an analysis dashboard with response histories, metrics and a short interpretation. Choose **Continue Testing** to return to tuning or **Exit** to close the program. Closing the application also saves an active run.

| Key | Action |
| --- | --- |
| Enter / Start button | Start the configured experiment |
| Hold W / S | Request positive / negative velocity; switches to tracking mode |
| Release W / S | Request zero velocity; the controller brakes |
| Space | Apply configured external force pulse; repeated pulses add |
| P | Pause/resume; physics time and logging pause together |
| R | Save current run and start a clean run with the same parameters |
| Escape / Finish button | Save the run and open its analysis dashboard |
| 1–6 in setup | PID, no controller, P-only, excessive gain, large push, tracking |
| Mouse drag in setup | Adjust any visible parameter with its slider |
| Mouse hover in setup | Explain the parameter and its effect on balance |
| Up / Down in setup | Select a parameter; list scrolls |
| Left / Right in setup | Adjust the selected parameter by one increment |
| E in setup | Type an exact value, then Enter; Escape cancels |
| Tab in setup | Switch balance / tracking mode |
| Q / Escape in setup | Exit |
| Enter / C in analysis | Continue testing and return to tuning |
| Q / Escape in analysis | Exit the program |

Window focus loss automatically pauses and clears held keys. W and S together request zero velocity. A/D are intentionally absent: this is one sagittal plane. Teal charts show actual values; amber charts show references or unsaturated commands. The stick figure follows the simulated body state, with rigid decorative limbs and no synthesized gait.

Interactive runs use **manual pushes and commands**. The large-push preset configures Space to apply 800 N for 0.35 s. Headless runs use the scripted protocol below.

## Reproducible experiments

```powershell
# All five required control experiments, plus velocity tracking
.\launch.bat --suite

# One reproducible experiment, no display required
.\launch.bat --headless --preset pid --duration 20
.\launch.bat --headless --preset no-controller
.\launch.bat --headless --preset tracking

# Reuse the last interactive settings, or your own JSON overrides
.\launch.bat --headless --config runs\last_config.json

# Automated GUI rendering check and preview image
.\launch.bat --screenshot runs\interface.png

# Regression tests
.\.runtime\python.exe -m unittest discover -s tests -v
```

All headless presets start at +3 degrees and receive the configured push at 4 s if they have not fallen. `tracking` requests +1 m/s at 2 s, -1 m/s at 8 s, and zero at 14 s. Other presets request zero throughout. A run stops at its first fall; an uncontrolled robot therefore falls before the scheduled push. Durations are rounded up to a whole physics step. Preset-specific overrides are applied after a supplied config.

Measured results from the supplied defaults, 0.01 s physics step and 20 s protocol:

| Preset | Result | Observed duration | Peak lean | Angle error RMS | Torque saturation |
| --- | --- | ---: | ---: | ---: | ---: |
| PID | Stable | 20.00 s | 3.00° | 0.50° | 0.35% |
| No controller | Fell | 0.91 s | 35.08° | 13.93° | 0.00% |
| P-only | Unsettled / oscillating | 20.00 s | 22.61° | 9.96° | 69.85% |
| Excessive gain | Unsettled / saturated | 20.00 s | 13.69° | 6.54° | 98.35% |
| Large disturbance | Fell | 4.22 s | 36.08° | 5.16° | 4.98% |
| Velocity tracking | Stable at end | 20.00 s | 6.57° | 1.23° | 1.00% |

Default PID recovers from the 100 N, 0.15 s push in **1.26 s after the pulse ends**, using the recovery definition below. The complete tracking protocol has velocity RMSE **0.474 m/s**, including the command reversals. Its early command windows do not meet the sustained ±0.1 m/s settling criterion before subsequent events, even though the final zero-command segment settles. A final “stable” status does not imply perfect tracking throughout the run.

P-only disables the outer loop, removes integral and derivative action, and retains Kp=1100. Excessive gain uses Kp=20000 with Ki=Kd=0 and disables the outer loop. The large-push preset retains default PID gains. These deliberate failures demonstrate the finite recovery envelope rather than claiming one tuning works universally. `runs/suite_summary.json` contains the measured results and artifact locations; running the suite again replaces this index but preserves every numbered run folder.

## Explicit model and assumptions

State is `[theta, omega, x, velocity]`, with theta measured clockwise from upright; rightward lean, force, motion and positive body torque have positive signs. The model has a point-mass rotational inertia `I = m h²` and uses these equations, implemented in `simulator/dynamics.py`:

```text
theta_dot = omega
omega_dot = (m*g*h*sin(theta) + torque + force*h*cos(theta) - b*omega) / (m*h*h)
x_dot     = velocity
v_dot     = g*sin(theta) - c*velocity + force/m
```

The angular model is a torque-driven inverted pendulum. Gravity destabilizes upright equilibrium. **Translation is a deliberately reduced, empirical lean-to-acceleration closure**: a lean produces forward acceleration, linear drag opposes speed, and an external push also affects translation. This closure represents an idealized translating support. It is not the coupled cart-pole equations or a mechanically complete humanoid. Translational acceleration does not feed a support-inertia term back into the angular equation, so the combined model is not energy-consistent multibody mechanics. The architecture is suitable for a transparent feedback-control study; numerical recovery envelopes are properties of this model, not predictions for real hardware.

There are no feet/contact transitions, traction limits, ground-reaction-force solver, step planner, actuator dynamics, sensor noise or lateral motion. The drawing is schematic. A future physically coupled model should replace the plant and retune controllers. For background on the distinction, see [MIT's Underactuated Robotics: cart-pole dynamics](https://underactuated.mit.edu/acrobot.html).

Defaults: mass 35 kg, COM height 0.8 m, gravity 9.81 m/s², ±80 Nm torque limit, angular damping 2 Nm·s/rad, translational drag coefficient 0.3 s⁻¹, ±35° fall boundary and ±10° requested lean limit. Fixed-step RK4 integrates the nonlinear plant at 100 Hz; controls and force are held constant over each step. Pygame renders at up to 60 Hz independently. A fall is detected after each physics step, so its final angle may slightly exceed 35°. GUI catch-up is capped at 0.1 s per frame; on a slow machine simulation time can lag wall-clock time.

## Controllers and tuning

The outer velocity PID outputs desired lean. The inner PID outputs body torque:

```text
velocity error = desired velocity - actual velocity
desired lean   = clamp(velocity PID, +/- lean limit)
angle error    = desired lean - actual lean
torque command = Kp * angle error + Ki * integral(angle error) - Kd * angular velocity
actual torque  = clamp(torque command, +/- torque limit)
```

Both PID implementations differentiate the measurement to avoid derivative kick on a setpoint change. Conditional integration prevents further windup into each loop's own limit; outer integration also freezes while the inner actuator was saturated on the previous step. Default inner gains are `(1100, 60, 260)` and outer gains `(0.06, 0.012, 0)`, all using radians and SI quantities. Derivative filtering is unnecessary for this noiseless V1; it would be needed when adding sensor noise.

Start by comparing no control, P-only and default PID. Drag the setup sliders to raise the push force, lower the torque limit or change one PID gain. Each slider covers a practical experiment range; press `E` to enter an exact value outside that range when needed. Compare plots before changing another parameter. Setup edits apply to the next experiment, and every run saves its full configuration. You can also edit `config/default.json`, or supply a partial override:

```json
{
  "balance": {"kp": 1100, "ki": 0, "kd": 260},
  "disturbance": {"force": 150, "duration": 0.15}
}
```

## Logs and metric definitions

Every started experiment gets the next numbered folder under `runs/`: `run1`, `run2`, `run3`, and so on. Each folder contains:

- `data.csv`: each completed physics interval, including state, desired state, errors, PID terms, commanded/actual torque, disturbance, saturation and fall flags.
- `config.json`: full configuration, preset, UTC creation time, model ID, integrator and units.
- `summary.json`: status, termination reason, scalar metrics and per-event responses.
- `report.png`: angle, velocity, torque and force plots with disturbance onset markers. No plot is made if the run ends before its first physics step; its summary says `no_data`.

CSV values use SI units; **angles are radians**, while screen/report labels and summary angle metrics use degrees. A row records the state at interval start and inputs applied during `[time, time + dt)`. `end_angle` and `end_velocity` retain the interval's resulting state, including the fall crossing. CSV buffers flush every 100 samples and at every normal finish/reset/close. An abrupt process kill may lose the final buffered samples and cannot generate reports.

Angle RMS uses `desired_angle - angle`, not raw lean. Velocity RMSE uses the requested velocity. Saturation percentage counts intervals where requested torque exceeds the actuator limit. Torque-squared integral is a control-effort proxy in Nm²·s, not mechanical energy. Peak lean includes terminal states. Falls are either zero or one because each run ends at the first fall.

Recovery requires angle error within ±2° and velocity error within ±0.1 m/s after a push ends, staying in band through the next command/push or run end with at least 0.5 s of observation. Recovery delay is measured from the end of the pulse. Command settling uses the velocity band and the same sustained-observation rule, measured from the command change. Disturbance peak deviation is relative to the lean at push onset; overshoot is the maximum deviation opposite the signed push from that same baseline. These are event-window observations, not extrapolations. `null` means unobserved/not measured, never zero. Largest recoverable force is left `null`: a single run cannot establish that envelope.

Status is `fell` if the threshold was crossed, `stable` if both errors remained within their bands over the final full second, or `unsettled` otherwise. This is an operational finite-run classification, not a proof of asymptotic stability.

## Source map and verification

```text
main.py                       CLI, scripted experiment/suite orchestration
config/default.json           Physical and control parameters
controllers/pid.py            PID, limits and anti-windup
controllers/velocity_controller.py  Outer loop
simulator/robot.py             State representation
simulator/dynamics.py          Explicit equations and RK4
simulator/environment.py       Fixed-step loop, pushes, falls, scripted inputs
visualization/app.py           Input, tuning, experiment lifecycle
visualization/renderer.py      Pygame schematic, telemetry, plots
analysis/logger.py            CSV and configuration snapshots
analysis/metrics.py           Error, control-effort and event metrics
analysis/report.py            JSON summaries and PNG reports
tests/test_simulator.py        Physics, controller, metrics and UI regressions
runs/                         Generated data and reports (Git-ignored)
```

Verification: 15 automated tests cover uncontrolled instability, stable recovery, forward/backward tracking, deliberate failures, torque saturation, PID decomposition, anti-windup, command semantics, pulse duration/overlap, mirrored initial states, timestep convergence, configuration validation, metric observation windows, output artifacts, and Pygame controls/pause/reset/tuning. The suite and actual renderer were exercised with SDL's dummy display, and the screenshot and report inspected. Physical keyboard/window behavior on this desktop has not been manually tested.

V1 intentionally stops at the handover's compact control study. LQR, realistic contact dynamics, estimator noise, parameter sweeps and 3D are future extensions.
