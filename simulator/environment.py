import copy
import math
from config import validate
from controllers.pid import PID
from controllers.velocity_controller import VelocityController
from .robot import State
from .dynamics import advance, derivative


class Environment:
    def __init__(self, config):
        self.config = validate(copy.deepcopy(config))
        self.dt = config["simulation"]["dt"]
        self.state = State(theta=math.radians(config["simulation"]["initial_angle_deg"]))
        self.balance = PID(**config["balance"], limit=config["robot"]["torque_limit"])
        self.velocity = VelocityController(config["velocity"], config["simulation"]["lean_limit_deg"])
        self.steps = 0
        self.desired_velocity = 0.0
        self.pushes = []
        self.saturated = False
        self.fell = False
        self.last = None

    @property
    def time(self):
        return self.steps * self.dt

    def push(self, force=None, duration=None):
        force = self.config["disturbance"]["force"] if force is None else force
        duration = self.config["disturbance"]["duration"] if duration is None else duration
        if not math.isfinite(force) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Push force must be finite and duration positive")
        # Durations quantized upward to whole physics steps; overlapping pushes add.
        self.pushes.append((self.steps + max(1, math.ceil(duration / self.dt - 1e-10)), force))

    def step(self):
        if self.fell:
            raise RuntimeError("Reset before stepping a fallen robot")
        self.pushes = [(end, force) for end, force in self.pushes if end > self.steps]
        force = sum(force for _, force in self.pushes)
        s, robot = self.state, self.config["robot"]
        acceleration = derivative(s.array(), 0, force, robot)[3]
        lean = self.velocity.step(self.desired_velocity, s.velocity, acceleration, self.dt, self.saturated)
        torque = self.balance.step(lean.actual - s.theta, s.omega, self.dt)
        next_state = advance(s, torque.actual, force, robot, self.dt)
        self.saturated = abs(torque.command) > robot["torque_limit"]
        self.fell = abs(next_state.theta) >= math.radians(robot["fall_angle_deg"])
        # Each row is the state at interval START, with input held for [t, t+dt).
        row = dict(time=self.time, dt=self.dt, position=s.x, velocity=s.velocity,
                   desired_velocity=self.desired_velocity, angle=s.theta,
                   desired_angle=lean.actual, angular_velocity=s.omega,
                   angle_error=lean.actual-s.theta, velocity_error=self.desired_velocity-s.velocity,
                   P_term=torque.p, I_term=torque.i, D_term=torque.d,
                   commanded_torque=torque.command, actual_torque=torque.actual,
                   disturbance_force=force, saturated=int(self.saturated), fell=int(self.fell),
                   end_angle=next_state.theta, end_velocity=next_state.velocity)
        self.state = next_state
        self.steps += 1
        self.last = row
        return row


def scripted_input(env, scenario):
    """Deterministic protocol shared by CLI runs and regression tests."""
    if env.steps == math.ceil(4.0 / env.dt - 1e-10):
        env.push()
    if scenario == "tracking":
        speed = env.config["simulation"]["command_speed"]
        env.desired_velocity = speed if 2 <= env.time < 8 else -speed if 8 <= env.time < 14 else 0.0
