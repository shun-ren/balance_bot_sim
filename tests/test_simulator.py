import copy
import csv
import math
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np

from config import load, preset, validate
from controllers.pid import PID
from simulator.environment import Environment, scripted_input
from simulator.dynamics import advance
from simulator.robot import State
from analysis.metrics import compute, settling_delay
from analysis.logger import RunLogger
from analysis.report import finish


def simulate(name="pid", seconds=20., config=None):
    config = preset(config or load(),name)
    env, rows = Environment(config), []
    for _ in range(math.ceil(seconds/env.dt)):
        scripted_input(env,name)
        rows.append(env.step())
        if env.fell:
            break
    return env,rows


class DynamicsTests(unittest.TestCase):
    def test_uncontrolled_instability_and_terminal_state(self):
        env,rows = simulate("no-controller")
        self.assertTrue(env.fell)
        self.assertLess(env.time,2)
        self.assertGreaterEqual(abs(rows[-1]["end_angle"]), math.radians(35))
        self.assertTrue(all(r["actual_torque"]==0 for r in rows))

    def test_default_recovery_and_tracking(self):
        env,rows = simulate()
        summary = compute(rows,env.config,"test")
        self.assertEqual(summary["status"],"stable")
        self.assertLess(summary["disturbance_events"][0]["recovery_after_push_s"],3)
        env,rows = simulate("tracking")
        self.assertFalse(env.fell)
        for t,target in [(7.,1.),(13.,-1.),(19.,0.)]:
            self.assertAlmostEqual(rows[round(t/env.dt)]["velocity"],target,delta=.2)

    def test_failure_presets(self):
        env,rows = simulate("large-disturbance")
        self.assertTrue(env.fell)
        self.assertGreater(env.time,4)
        env,rows = simulate("excessive-gain")
        self.assertGreater(compute(rows,env.config,"test")["saturation_percent"],90)
        env,rows = simulate("p-only")
        self.assertGreater(np.std([r["angle"] for r in rows[-500:]]),math.radians(5))

    def test_torque_limit_and_pid_decomposition(self):
        env,rows = simulate("excessive-gain",seconds=3)
        for r in rows:
            self.assertLessEqual(abs(r["actual_torque"]),80)
            self.assertAlmostEqual(r["commanded_torque"], r["P_term"]+r["I_term"]+r["D_term"])

    def test_physics_saturation_is_defensive(self):
        c=load()["robot"]
        a=advance(State(),10000,0,c,.01)
        b=advance(State(),80,0,c,.01)
        np.testing.assert_array_equal(a.array(),b.array())

    def test_command_never_teleports_state(self):
        e=Environment(load())
        before=e.state.array().copy()
        e.desired_velocity=1
        np.testing.assert_array_equal(before,e.state.array())
        e.step()
        self.assertLess(abs(e.state.velocity),.01)

    def test_push_duration_and_addition(self):
        e=Environment(load())
        e.push(10,.15)
        e.push(20,.05)
        forces=[e.step()["disturbance_force"] for _ in range(20)]
        self.assertEqual(forces,[30]*5+[10]*10+[0]*5)
        self.assertAlmostEqual(sum(forces)*e.dt,2.5)

    def test_mirrored_initial_conditions(self):
        c=load()
        c["simulation"]["initial_angle_deg"] *= -1
        a,_=simulate(seconds=3)
        b,_=simulate(seconds=3,config=c)
        np.testing.assert_allclose(a.state.array(),-b.state.array(),atol=1e-12)

    def test_timestep_convergence(self):
        coarse,_=simulate("tracking")
        c=load()
        c["simulation"]["dt"] /= 2
        fine,_=simulate("tracking",config=c)
        np.testing.assert_allclose(coarse.state.array(),fine.state.array(),atol=.015)


class ControllerAndMetricsTests(unittest.TestCase):
    def test_antiwindup_and_no_setpoint_derivative_kick(self):
        pid=PID(10,5,2,1)
        for _ in range(1000):
            result=pid.step(10,0,.01)
        self.assertEqual(result.i,0)
        self.assertEqual(result.d,0)
        self.assertLess(pid.step(-.01,0,.01).actual,0)

    def test_invalid_config(self):
        for group,key,value in [("robot","mass",0),("simulation","dt",1),
                                 ("balance","kp",float("nan")),("robot","velocity_drag",-1)]:
            c=load(); c[group][key]=value
            with self.assertRaises(ValueError): validate(c)

    def test_settling_requires_sustained_observation(self):
        t=np.arange(20)*.1
        self.assertIsNone(settling_delay(t,np.array([False]*17+[True]*3),0,20))
        self.assertAlmostEqual(settling_delay(t,np.array([False]*5+[True]*15),0,20),.5)

    def test_no_events_are_not_invented(self):
        e,rows=simulate(seconds=2)
        s=compute(rows,e.config,"test")
        self.assertEqual(s["disturbance_events"],[])
        self.assertEqual(s["tracking_events"],[])
        self.assertIsNone(s["largest_recoverable_disturbance_N"])

    def test_logging_and_report_artifacts(self):
        e,rows=simulate(seconds=.2)
        with tempfile.TemporaryDirectory() as directory:
            logger=RunLogger(directory,e.config,"test")
            for row in rows: logger.append(row)
            result=finish(logger,"test_finished")
            self.assertEqual(result["samples"],20)
            run_directory = Path(directory) / "run1"
            self.assertTrue(run_directory.is_dir())
            self.assertEqual({path.name for path in run_directory.iterdir()},
                             {"data.csv", "config.json", "summary.json", "report.png"})
            with (run_directory / "data.csv").open() as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),20)


class InterfaceTests(unittest.TestCase):
    def test_controls_pause_reset_and_tuning(self):
        os.environ["SDL_VIDEODRIVER"]="dummy"
        os.environ["SDL_AUDIODRIVER"]="dummy"
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"]="1"
        import pygame
        from visualization.app import App
        with tempfile.TemporaryDirectory() as directory:
            app=App(load(),"pid",directory)
            def key(k): app.event(pygame.event.Event(pygame.KEYDOWN,key=k,unicode=""))
            try:
                key(pygame.K_RETURN)
                key(pygame.K_w)
                app.tick(.1)
                self.assertEqual(app.env.desired_velocity,1)
                key(pygame.K_p)
                steps=app.env.steps
                app.tick(.1)
                self.assertEqual(app.env.steps,steps)
                key(pygame.K_p)
                key(pygame.K_SPACE)
                app.tick(.02)
                self.assertEqual(app.env.last["disturbance_force"],100)
                key(pygame.K_r)
                self.assertEqual(app.env.steps,0)
                self.assertFalse(app.env.pushes)
                app.tick(.02)
                key(pygame.K_ESCAPE)
                self.assertFalse(app.running)
                self.assertTrue(app.analysis_view)
                self.assertIsNotNone(app.summary)
                self.assertEqual(len(list(Path(directory).glob("run*/report.png"))),2)
                app.renderer.draw(app)
                app.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=(850,750)))
                self.assertFalse(app.analysis_view)
                self.assertTrue(app.change_value(1200))
                app.event(pygame.event.Event(pygame.MOUSEMOTION,pos=(850,184),rel=(0,0),buttons=(0,0,0)))
                self.assertEqual(app.hovered_field,0)
                # Clicking and dragging the first slider adjusts Balance Kp.
                app.selected = 0
                app.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=(1014,204)))
                self.assertAlmostEqual(app.config["balance"]["kp"],10000,delta=50)
                app.event(pygame.event.Event(pygame.MOUSEMOTION,pos=(1190,204),rel=(176,0),buttons=(1,0,0)))
                self.assertEqual(app.config["balance"]["kp"],20000)
                app.event(pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=(1190,204)))
                self.assertIsNone(app.dragging_slider)
                app.renderer.draw(app)
                app.analysis_view=True
                self.assertFalse(app.event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,button=1,pos=(1100,750))))
            finally:
                pygame.quit()


if __name__ == "__main__":
    unittest.main()
