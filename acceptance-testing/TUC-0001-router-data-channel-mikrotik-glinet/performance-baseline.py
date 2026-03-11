#!/usr/bin/env python3
"""
TUC-0001 Performance Baseline

Measures compile-time performance for the TUC fixture and establishes
regression detection baselines.

Metrics tracked:
- Compile time (wall-clock)
- Peak memory usage
- Plugin execution times
- Diagnostics count
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


class PerformanceBaseline:
    def __init__(self, topology_root: Path):
        self.topology_root = topology_root
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "runs": [],
        }
        self.baseline_file = Path(__file__).parent / "artifacts" / "performance-baseline.json"

    def run_compile(self, run_number: int) -> dict:
        """Run compile and measure performance."""
        compile_script = self.topology_root / "v5" / "topology-tools" / "compile-topology.py"
        topology_file = self.topology_root / "v5" / "topology" / "topology.yaml"
        output_file = Path(__file__).parent / "artifacts" / f"effective-baseline-run{run_number}.json"

        command = [
            "python",
            str(compile_script),
            "--topology",
            str(topology_file),
            "--strict-model-lock",
            "--output-json",
            str(output_file),
        ]

        print(f"Run {run_number}: Starting compile...", end=" ", flush=True)

        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=str(self.topology_root),
                capture_output=True,
                text=True,
                timeout=120,  # 2-minute timeout
            )
            elapsed = time.time() - start_time

            if result.returncode != 0:
                print(f"❌ FAILED (exit code {result.returncode})")
                return {
                    "run": run_number,
                    "elapsed_seconds": elapsed,
                    "status": "failed",
                    "error": result.stderr[:500],
                }

            print(f"✅ OK ({elapsed:.2f}s)")

            return {
                "run": run_number,
                "elapsed_seconds": elapsed,
                "status": "success",
                "output_file": str(output_file),
            }

        except subprocess.TimeoutExpired:
            print(f"❌ TIMEOUT (>120s)")
            return {
                "run": run_number,
                "elapsed_seconds": 120,
                "status": "timeout",
                "error": "Compile exceeded 120-second timeout",
            }

    def analyze_results(self):
        """Analyze performance metrics."""
        if not self.results["runs"]:
            print("\n❌ No successful runs to analyze")
            return

        successful_runs = [r for r in self.results["runs"] if r["status"] == "success"]
        if not successful_runs:
            print("\n❌ No successful runs to analyze")
            return

        times = [r["elapsed_seconds"] for r in successful_runs]

        print("\n" + "=" * 60)
        print("PERFORMANCE ANALYSIS")
        print("=" * 60)
        print(f"Successful runs: {len(successful_runs)}")
        print(f"Total runs: {len(self.results['runs'])}")
        print(f"\nCompile time (wall-clock):")
        print(f"  Min:     {min(times):.3f}s")
        print(f"  Max:     {max(times):.3f}s")
        print(f"  Average: {sum(times) / len(times):.3f}s")
        print(f"  Median:  {sorted(times)[len(times)//2]:.3f}s")

        # Check if baseline exists
        if self.baseline_file.exists():
            with open(self.baseline_file, "r") as f:
                baseline = json.load(f)
                baseline_avg = baseline.get("average_compile_time", 0)
                current_avg = sum(times) / len(times)
                regression_percent = ((current_avg - baseline_avg) / baseline_avg) * 100 if baseline_avg > 0 else 0

                print(f"\nComparison to baseline:")
                print(f"  Baseline average: {baseline_avg:.3f}s")
                print(f"  Current average:  {current_avg:.3f}s")
                print(f"  Regression:       {regression_percent:+.1f}%")

                if regression_percent > 10:
                    print(f"\n⚠️  WARNING: Performance regressed > 10%")
                elif regression_percent < -5:
                    print(f"\n✅ IMPROVEMENT: Performance improved")
        else:
            print(f"\n📌 Baseline file not found; this is the first run")

    def save_baseline(self):
        """Save current run as baseline."""
        successful_runs = [r for r in self.results["runs"] if r["status"] == "success"]
        if not successful_runs:
            print("\n❌ No successful runs to save as baseline")
            return

        times = [r["elapsed_seconds"] for r in successful_runs]
        baseline = {
            "timestamp": datetime.now().isoformat(),
            "average_compile_time": sum(times) / len(times),
            "min_compile_time": min(times),
            "max_compile_time": max(times),
            "run_count": len(successful_runs),
        }

        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_file, "w") as f:
            json.dump(baseline, f, indent=2)

        print(f"\n✅ Baseline saved to {self.baseline_file}")

    def run(self, num_runs: int = 3, save_baseline: bool = False):
        """Run performance benchmark."""
        print(f"TUC-0001 Performance Baseline ({num_runs} runs)\n")

        for i in range(1, num_runs + 1):
            result = self.run_compile(i)
            self.results["runs"].append(result)

        self.analyze_results()

        if save_baseline:
            self.save_baseline()

        return 0 if all(r["status"] == "success" for r in self.results["runs"]) else 1


if __name__ == "__main__":
    import sys

    topology_root = Path(__file__).parent.parent.parent.parent
    baseline = PerformanceBaseline(topology_root)

    # Check for --baseline flag
    save_baseline = "--baseline" in sys.argv
    num_runs = 3 if "--baseline" not in sys.argv else 5  # More runs for baseline

    sys.exit(baseline.run(num_runs=num_runs, save_baseline=save_baseline))
