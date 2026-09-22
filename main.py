"""Interactive lab, reproducible headless experiments and comparison suite."""
import argparse
import json
import math
import os
from pathlib import Path
from config import ROOT, PRESETS, load, preset, validate
from simulator.environment import Environment, scripted_input
from analysis.logger import RunLogger
from analysis.report import finish


def run_headless(config, scenario, output):
    env = Environment(config)
    logger = RunLogger(output,config,scenario)
    reason = "duration_complete"
    try:
        for _ in range(math.ceil(config["simulation"]["duration"]/env.dt-1e-10)):
            scripted_input(env,scenario)
            logger.append(env.step())
            if env.fell:
                reason = "fall_threshold"
                break
    except KeyboardInterrupt:
        reason = "interrupted"
    except BaseException:
        logger.close()
        raise
    summary = finish(logger,reason)
    print(f'{scenario:18s} {summary["status"]:10s}  {summary["duration_s"]:6.2f}s  '
          f'lean {summary.get("max_lean_deg",0):6.2f} deg  sat {summary.get("saturation_percent",0):5.1f}%')
    print(f"  {logger.directory}")
    return dict(summary, artifacts=str(logger.directory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless",action="store_true",help="Run a deterministic protocol without a window")
    parser.add_argument("--suite",action="store_true",help="Run all six comparison presets and save reports")
    parser.add_argument("--preset",choices=PRESETS,default="pid")
    parser.add_argument("--config",type=Path,help="JSON overrides for default parameters")
    parser.add_argument("--duration",type=float,help="Experiment duration in simulation seconds")
    parser.add_argument("--output",type=Path,default=ROOT/"runs")
    parser.add_argument("--screenshot",type=Path,help="Run UI smoke test and save one frame")
    args = parser.parse_args()
    try:
        config = load(args.config)
        if args.duration is not None:
            config["simulation"]["duration"] = args.duration
        validate(config)
    except (ValueError,OSError) as exc:
        parser.error(str(exc))
    if args.suite:
        results = [run_headless(preset(config,name),name,args.output) for name in PRESETS]
        (args.output/"suite_summary.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    elif args.headless:
        run_headless(preset(config,args.preset),args.preset,args.output)
    else:
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        if args.screenshot:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["SDL_AUDIODRIVER"] = "dummy"
            args.screenshot.parent.mkdir(parents=True,exist_ok=True)
        from visualization.app import App
        App(config,args.preset,args.output).run(args.screenshot)


if __name__ == "__main__":
    main()
