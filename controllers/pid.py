"""PID with derivative on measurement and conditional-integration anti-windup."""
from dataclasses import dataclass


@dataclass
class PIDOutput:
    command: float
    actual: float
    p: float
    i: float
    d: float


class PID:
    def __init__(self, kp, ki, kd, limit):
        self.kp, self.ki, self.kd, self.limit = kp, ki, kd, limit
        self.integral = 0.0

    def step(self, error, measurement_rate, dt, freeze_integral=False):
        p, d = self.kp * error, -self.kd * measurement_rate
        candidate = self.integral + error * dt
        trial = p + self.ki * candidate + d
        # Integrate only when not pushing further into saturation.
        if not freeze_integral and (abs(trial) <= self.limit or trial * error < 0):
            self.integral = candidate
        i = self.ki * self.integral
        command = p + i + d
        return PIDOutput(command, max(-self.limit, min(self.limit, command)), p, i, d)
