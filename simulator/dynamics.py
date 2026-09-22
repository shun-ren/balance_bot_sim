"""Reduced-order plant; see README for the translational closure's limitations.

theta'' = (m*g*h*sin(theta) + tau + F*h*cos(theta) - b*omega)/(m*h**2)
x''     = g*sin(theta) - c*v + F/m

Positive lean, torque, push and translation point right. Translation uses an
empirical lean-to-acceleration closure, NOT full cart-pole/contact mechanics.
Both states are integrated; commands never assign position or velocity.
"""
import numpy as np
from .robot import State


def derivative(state, torque, force, robot):
    theta, omega, _, velocity = state
    m, h, g = robot["mass"], robot["height"], robot["gravity"]
    angular_acceleration = (m * g * h * np.sin(theta) + torque
                            + force * h * np.cos(theta)
                            - robot["angular_damping"] * omega) / (m * h * h)
    acceleration = g * np.sin(theta) - robot["velocity_drag"] * velocity + force / m
    return np.array([omega, angular_acceleration, velocity, acceleration])


def advance(state, torque, force, robot, dt):
    """Fourth-order Runge-Kutta; zero-order hold of control/force per step."""
    y = state.array()
    torque = float(np.clip(torque, -robot["torque_limit"], robot["torque_limit"]))
    k1 = derivative(y, torque, force, robot)
    k2 = derivative(y + dt * k1 / 2, torque, force, robot)
    k3 = derivative(y + dt * k2 / 2, torque, force, robot)
    k4 = derivative(y + dt * k3, torque, force, robot)
    return State(*(y + dt * (k1 + 2*k2 + 2*k3 + k4) / 6))
