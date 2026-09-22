"""Validated, reproducible experiment configuration."""
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ("pid", "no-controller", "p-only", "excessive-gain", "large-disturbance", "tracking")


def validate(config):
    for group, values in config.items():
        for key, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{group}.{key} must be a finite number")
    for group, keys in {"robot": ("mass", "height", "gravity", "torque_limit", "fall_angle_deg"),
                        "simulation": ("dt", "duration", "lean_limit_deg", "command_speed"),
                        "disturbance": ("duration",)}.items():
        for key in keys:
            if config[group][key] <= 0:
                raise ValueError(f"{group}.{key} must be positive")
    if not 0.001 <= config["simulation"]["dt"] <= 0.02:
        raise ValueError("simulation.dt must be between 0.001 and 0.02 seconds")
    if not 0 < config["simulation"]["lean_limit_deg"] < config["robot"]["fall_angle_deg"] < 85:
        raise ValueError("Require 0 < lean limit < fall angle < 85 degrees")
    if abs(config["simulation"]["initial_angle_deg"]) >= config["robot"]["fall_angle_deg"]:
        raise ValueError("Initial angle must be inside the fall boundary")
    for key in ("angular_damping", "velocity_drag"):
        if config["robot"][key] < 0:
            raise ValueError(f"robot.{key} cannot be negative")
    for group in ("balance", "velocity"):
        if any(value < 0 for value in config[group].values()):
            raise ValueError(f"{group} gains cannot be negative")
    return config


def load(path=None):
    with open(ROOT / "config" / "default.json", encoding="utf-8") as stream:
        config = json.load(stream)
    if path:
        with open(path, encoding="utf-8") as stream:
            overrides = json.load(stream)
        for group, values in overrides.items():
            if group not in config or not isinstance(values, dict):
                raise ValueError(f"Unknown configuration group: {group}")
            for key, value in values.items():
                if key not in config[group]:
                    raise ValueError(f"Unknown parameter: {group}.{key}")
                config[group][key] = value
    return validate(config)


def preset(config, name):
    result = copy.deepcopy(config)
    if name == "no-controller":
        result["balance"] = dict(kp=0., ki=0., kd=0.)
        result["velocity"] = dict(kp=0., ki=0., kd=0.)
    elif name == "p-only":
        result["balance"].update(ki=0., kd=0.)
        result["velocity"] = dict(kp=0., ki=0., kd=0.)
    elif name == "excessive-gain":
        result["balance"].update(kp=20000., ki=0., kd=0.)
        result["velocity"] = dict(kp=0., ki=0., kd=0.)
    elif name == "large-disturbance":
        result["disturbance"].update(force=800., duration=0.35)
    elif name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    return validate(result)
