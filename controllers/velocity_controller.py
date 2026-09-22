import math
from .pid import PID


class VelocityController:
    def __init__(self, gains, lean_limit_deg):
        self.pid = PID(**gains, limit=math.radians(lean_limit_deg))

    def step(self, desired_velocity, velocity, acceleration, dt, actuator_saturated=False):
        return self.pid.step(desired_velocity - velocity, acceleration, dt,
                             freeze_integral=actuator_saturated)
