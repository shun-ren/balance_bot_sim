from dataclasses import dataclass
import numpy as np


@dataclass
class State:
    theta: float = 0.0
    omega: float = 0.0
    x: float = 0.0
    velocity: float = 0.0

    def array(self):
        return np.array([self.theta, self.omega, self.x, self.velocity], dtype=float)
