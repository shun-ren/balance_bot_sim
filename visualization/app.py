import copy
import json
import math
from pathlib import Path
import pygame
from config import PRESETS, preset, validate
from simulator.environment import Environment
from analysis.logger import RunLogger
from analysis.report import finish
from .renderer import (Renderer, FIELDS, slider_rect, field_at_position,
                       CONTINUE_RECT, EXIT_RECT)


class App:
    def __init__(self, config, scenario, output):
        self.base_config = copy.deepcopy(config)
        self.config = preset(config, scenario)
        self.scenario, self.output = scenario, Path(output)
        self.env = Environment(self.config)
        self.renderer = Renderer()
        self.running = self.paused = self.editing = False
        self.mode = "tracking" if scenario == "tracking" else "balance"
        self.selected, self.edit_text, self.message = 0, "", ""
        self.logger = self.summary = None
        self.previous_rows = []
        self.accumulator = 0.
        self.held = set()
        self.dragging_slider = None
        self.hovered_field = None
        self.analysis_view = False
        self.last_run_directory = None

    def start(self):
        validate(self.config)
        self.analysis_view = False
        self.hovered_field = None
        self.env = Environment(self.config)
        self.logger = RunLogger(self.output,self.config,"interactive-"+self.scenario)
        self.logger.metadata["interactive_mode"] = self.mode
        # Persist a convenient editable copy of the latest tuning as well as run metadata.
        (self.output / "last_config.json").write_text(json.dumps(self.config,indent=2),encoding="utf-8")
        self.running, self.paused = True, False
        self.accumulator = 0.
        self.held.clear()
        self.message = "Run started. W/S request velocity in tracking mode; SPACE injects a push."

    def stop(self, reason):
        if not self.running:
            return
        self.running = False
        self.paused = False
        self.held.clear()
        self.env.desired_velocity = 0.
        self.message = "Saving CSV, summary and plots..."
        self.renderer.draw(self)
        self.summary = finish(self.logger, reason)
        self.previous_rows = self.logger.rows
        self.last_run_directory = self.logger.directory
        self.message = "Saved "+self.logger.directory.name+" (CSV / JSON / PNG)"
        print(self.message, flush=True)
        self.logger = None
        self.analysis_view = True

    def continue_testing(self):
        self.analysis_view = False
        self.hovered_field = None
        self.message = "Previous run saved. Adjust one parameter, then start the next experiment."

    def change_value(self, value):
        _,group,key,_,_,_ = FIELDS[self.selected]
        candidate = copy.deepcopy(self.config)
        candidate[group][key] = value
        try:
            validate(candidate)
        except ValueError as exc:
            self.message = str(exc)
            return False
        self.config = candidate
        self.env = Environment(self.config)
        self.message = "Parameters updated for the next experiment."
        return True

    def set_slider_from_mouse(self, index, mouse_x):
        self.selected = index
        _,_,_,step,minimum,maximum = FIELDS[index]
        track = slider_rect(index, self.selected)
        ratio = max(0., min(1., (mouse_x-track.left)/track.width))
        value = minimum + ratio * (maximum-minimum)
        value = round(round(value/step)*step, 8)
        return self.change_value(max(minimum, min(maximum, value)))

    def event(self, event):
        if event.type == pygame.QUIT:
            self.stop("window_closed")
            return False
        if event.type == pygame.WINDOWFOCUSLOST:
            self.held.clear()
            if self.running:
                self.paused = True
        if event.type == pygame.KEYUP:
            self.held.discard(event.key)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_slider = None
        if event.type == pygame.MOUSEMOTION and not self.running and not self.analysis_view:
            if self.dragging_slider is not None:
                self.set_slider_from_mouse(self.dragging_slider,event.pos[0])
            self.hovered_field = field_at_position(event.pos,self.selected)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.analysis_view:
                if CONTINUE_RECT.collidepoint(event.pos):
                    self.continue_testing()
                elif EXIT_RECT.collidepoint(event.pos):
                    return False
            elif pygame.Rect(1020,731,172,42).collidepoint(event.pos):
                if self.running:
                    self.stop("user_finished")
                elif not self.editing:
                    self.start()
            elif not self.running and not self.editing:
                for index in range(len(FIELDS)):
                    track = slider_rect(index,self.selected)
                    if track and track.inflate(0,10).collidepoint(event.pos):
                        self.dragging_slider = index
                        self.set_slider_from_mouse(index,event.pos[0])
                        break
        if event.type != pygame.KEYDOWN:
            return True
        key = event.key
        self.held.add(key)
        if self.analysis_view:
            if key in (pygame.K_RETURN,pygame.K_c):
                self.continue_testing()
            elif key in (pygame.K_q,pygame.K_ESCAPE):
                return False
            return True
        if self.running:
            if key == pygame.K_ESCAPE:
                self.stop("user_finished")
            elif key == pygame.K_r:
                self.stop("reset")
                self.start()
            elif key == pygame.K_p:
                self.paused = not self.paused
                self.held.clear()
            elif key == pygame.K_SPACE and not self.paused:
                self.env.push()
            elif key in (pygame.K_w, pygame.K_s) and self.mode == "balance":
                self.mode = "tracking"
                self.message = "Tracking mode: release W/S to request zero velocity."
            return True
        if self.editing:
            if key == pygame.K_ESCAPE:
                self.editing = False
            elif key == pygame.K_RETURN:
                try:
                    if self.change_value(float(self.edit_text)):
                        self.editing = False
                except ValueError:
                    self.message = "Enter a finite number."
            elif key == pygame.K_BACKSPACE:
                self.edit_text = self.edit_text[:-1]
            elif event.unicode in "0123456789.-+eE" and len(self.edit_text)<16:
                self.edit_text += event.unicode
            return True
        if key in (pygame.K_q,pygame.K_ESCAPE):
            return False
        if key == pygame.K_RETURN:
            self.start()
        elif key == pygame.K_TAB:
            self.mode = "balance" if self.mode == "tracking" else "tracking"
        elif key in (pygame.K_UP,pygame.K_DOWN):
            self.selected = (self.selected + (1 if key == pygame.K_DOWN else -1)) % len(FIELDS)
            self.hovered_field = None
        elif key in (pygame.K_LEFT,pygame.K_RIGHT):
            _,group,param,step,_,_ = FIELDS[self.selected]
            self.change_value(round(self.config[group][param] + step*(1 if key==pygame.K_RIGHT else -1),8))
        elif key == pygame.K_e:
            self.editing, self.edit_text = True, ""
        elif pygame.K_1 <= key <= pygame.K_6:
            self.scenario = PRESETS[key-pygame.K_1]
            self.config = preset(self.base_config,self.scenario)
            self.env = Environment(self.config)
            self.mode = "tracking" if self.scenario=="tracking" else "balance"
            self.hovered_field = None
            self.message = "Loaded preset: "+self.scenario
        return True

    def tick(self, elapsed):
        if not self.running or self.paused:
            self.accumulator = 0.
            return
        self.env.desired_velocity = self.config["simulation"]["command_speed"] * (
            int(pygame.K_w in self.held)-int(pygame.K_s in self.held)) if self.mode=="tracking" else 0.
        self.accumulator += min(elapsed,0.1)
        while self.accumulator >= self.env.dt and self.running:
            self.logger.append(self.env.step())
            self.accumulator -= self.env.dt
            if self.env.fell:
                self.stop("fall_threshold")
            elif self.env.time >= self.config["simulation"]["duration"]-1e-9:
                self.stop("duration_complete")

    def run(self, screenshot=None):
        clock = pygame.time.Clock()
        try:
            if screenshot:
                # Exercise the actual renderer and lifecycle without requiring a display.
                self.start()
                self.mode = "tracking"
                self.held.add(pygame.K_w)
                for _ in range(160):
                    self.tick(1/60)
                self.env.push()
                self.tick(.02)
                self.renderer.draw(self)
                pygame.image.save(self.renderer.screen,str(screenshot))
                self.stop("render_smoke_test")
                return
            active = True
            while active:
                elapsed = clock.tick(60)/1000.
                for event in pygame.event.get():
                    if not self.event(event):
                        active = False
                        break
                if active:
                    self.tick(elapsed)
                    self.renderer.draw(self)
        finally:
            if self.running:
                self.stop("application_exit")
            pygame.quit()
