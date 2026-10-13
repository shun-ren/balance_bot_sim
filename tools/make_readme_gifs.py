"""Render short README demonstrations from the real simulator UI.

This is intentionally a small artifact generator rather than a fake animation:
all frames come from the same Renderer used by main.py.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import copy
import tempfile
from pathlib import Path

import pygame
from PIL import Image

from analysis.metrics import compute
from config import load, preset
from simulator.environment import Environment
from visualization.app import App


class CaptureLogger:
    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(row)


def frame(app):
    app.renderer.draw(app)
    surface = app.renderer.screen.copy()
    image = Image.frombytes("RGB", surface.get_size(), pygame.image.tostring(surface, "RGB"))
    return image.resize((930, 615), Image.Resampling.LANCZOS)


def live_app(scenario):
    config = preset(load(), scenario)
    config["simulation"]["duration"] = 120
    app = App(config, scenario, tempfile.mkdtemp(prefix="balance_lab_gif_"))
    app.logger = CaptureLogger()
    app.running = True
    app.mode = "balance"
    return app


def workflow_frames():
    app = live_app("pid")
    frames = []
    app.running = False
    app.hovered_field = 14
    for _ in range(6):
        frames.append(frame(app))
    app.running = True
    app.hovered_field = None
    for step in range(360):
        if step == 100:
            app.env.push(160, .15)
        app.tick(app.env.dt)
        if step % 6 == 0:
            frames.append(frame(app))
    app.running = False
    app.analysis_view = True
    app.summary = compute(app.logger.rows, app.config, "demo_complete")
    app.summary["scenario"] = "pid"
    app.previous_rows = app.logger.rows
    for _ in range(8):
        frames.append(frame(app))
    return frames


def failure_frames():
    frames = []
    for scenario in ("no-controller", "excessive-gain"):
        app = live_app(scenario)
        for step in range(180):
            app.logger.append(app.env.step())
            if step % 5 == 0:
                frames.append(frame(app))
            if app.env.fell:
                break
        app.running = False
        app.analysis_view = True
        app.summary = compute(app.logger.rows, app.config, "fall_threshold" if app.env.fell else "demo_complete")
        app.summary["scenario"] = scenario
        app.previous_rows = app.logger.rows
        for _ in range(5):
            frames.append(frame(app))
    return frames


def hover_frames():
    """Pause on real parameter help cards so the README teaches the controls."""
    app = live_app("pid")
    app.running = False
    frames = []
    for index in (0, 14, 9, 2):
        app.selected = index
        app.hovered_field = index
        for _ in range(10):
            frames.append(frame(app))
    return frames


def save_gif(images, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:], duration=100,
                   loop=0, optimize=True, disposal=2)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    pygame.init()
    pygame.display.set_mode((1240, 820))
    save_gif(workflow_frames(), root / "assets" / "balance_lab.gif")
    save_gif(failure_frames(), root / "assets" / "failure_modes.gif")
    save_gif(hover_frames(), root / "assets" / "parameter_help.gif")
    pygame.quit()
