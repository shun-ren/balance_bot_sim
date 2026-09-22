import csv
import json
from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, directory, config, scenario):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = self._create_run_directory(directory)
        self.base = self.directory / "run"
        self.file = (self.directory / "data.csv").open("x", newline="", encoding="utf-8")
        self.writer = None
        self.rows = []
        self.metadata = dict(created_utc=datetime.now(timezone.utc).isoformat(), scenario=scenario, config=config,
                             model="reduced_lean_pendulum_v1", integrator="RK4",
                             row_convention="state at interval start; inputs held over dt",
                             units="SI (angles in radians, torque in Nm, force in N)")
        (self.directory / "config.json").write_text(
            json.dumps(self.metadata, indent=2), encoding="utf-8")

    @staticmethod
    def _create_run_directory(directory):
        """Create the next available runN directory without overwriting prior runs."""
        number = 1
        while True:
            run_directory = directory / f"run{number}"
            try:
                run_directory.mkdir()
                return run_directory
            except FileExistsError:
                number += 1

    def append(self, row):
        if self.writer is None:
            self.writer = csv.DictWriter(self.file, fieldnames=list(row))
            self.writer.writeheader()
        self.writer.writerow(row)
        self.rows.append(row)
        if len(self.rows) % 100 == 0:
            self.file.flush()

    def close(self):
        self.file.close()
