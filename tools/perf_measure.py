"""Automated performance measurement tool for SRPSS.

Measures CPU usage, memory, and frame timing to detect performance regressions.
Designed to show that 2.5 baseline is better than 2.6 current state.
"""
import subprocess
import time
import psutil
import sys
from pathlib import Path
from typing import Optional, Dict, List
import json


class PerformanceMeasurement:
    """Measure application performance metrics."""
    
    def __init__(self, app_path: Path, duration_seconds: int = 15):
        self.app_path = app_path
        self.duration = duration_seconds
        self.process: Optional[psutil.Process] = None
        self.cpu_samples: List[float] = []
        self.memory_samples: List[int] = []
        
    def start_app(self) -> bool:
        """Start the application and get process handle."""
        try:
            # Start app with perf metrics enabled
            env = {
                "SRPSS_PERF_METRICS": "1",
                "SRPSS_DISABLE_LOGGING": "0",
            }
            
            cmd = [sys.executable, str(self.app_path / "main.py")]
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.app_path),
                env={**subprocess.os.environ, **env},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            # Wait for process to initialize and become measurable
            time.sleep(4)
            
            # Verify process is still running
            if proc.poll() is not None:
                print(f"Process exited immediately with code {proc.returncode}")
                return False
            
            # Get psutil handle
            try:
                self.process = psutil.Process(proc.pid)
                # Force initial CPU measurement
                self.process.cpu_percent(interval=0.1)
                return True
            except psutil.NoSuchProcess:
                print(f"Process {proc.pid} not found")
                return False
            
        except Exception as e:
            print(f"Failed to start app: {e}")
            return False
    
    def measure(self) -> Dict[str, float]:
        """Measure performance for configured duration."""
        if not self.process:
            return {}
        
        print(f"Measuring for {self.duration} seconds...")
        start_time = time.time()
        sample_interval = 0.5  # Sample every 500ms
        
        while (time.time() - start_time) < self.duration:
            try:
                # CPU percentage (per-core)
                cpu = self.process.cpu_percent(interval=0.1)
                self.cpu_samples.append(cpu)
                
                # Memory in MB
                mem_info = self.process.memory_info()
                mem_mb = mem_info.rss / (1024 * 1024)
                self.memory_samples.append(mem_mb)
                
                time.sleep(sample_interval)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print("Process terminated or access denied")
                break
        
        # Calculate statistics
        if not self.cpu_samples:
            return {}
        
        cpu_avg = sum(self.cpu_samples) / len(self.cpu_samples)
        cpu_min = min(self.cpu_samples)
        cpu_max = max(self.cpu_samples)
        cpu_p95 = sorted(self.cpu_samples)[int(len(self.cpu_samples) * 0.95)]
        
        mem_avg = sum(self.memory_samples) / len(self.memory_samples)
        mem_max = max(self.memory_samples)
        
        return {
            "cpu_avg": cpu_avg,
            "cpu_min": cpu_min,
            "cpu_max": cpu_max,
            "cpu_p95": cpu_p95,
            "memory_avg_mb": mem_avg,
            "memory_max_mb": mem_max,
            "samples": len(self.cpu_samples),
        }
    
    def stop_app(self):
        """Stop the application."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    self.process.kill()
                except psutil.NoSuchProcess:
                    pass
    
    def parse_perf_log(self) -> Dict[str, any]:
        """Parse performance log for frame timing data."""
        log_path = self.app_path / "logs" / "screensaver_perf.log"
        if not log_path.exists():
            return {}
        
        frame_times = []
        paint_times = []
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Look for frame timing data
                    if "[PERF]" in line and "dt=" in line:
                        # Extract dt value
                        try:
                            dt_str = line.split("dt=")[1].split()[0].rstrip("ms")
                            frame_times.append(float(dt_str))
                        except (IndexError, ValueError):
                            pass
                    
                    # Look for paint timing
                    if "[PERF_WIDGET]" in line and "avg_ms=" in line:
                        try:
                            avg_str = line.split("avg_ms=")[1].split()[0]
                            paint_times.append(float(avg_str))
                        except (IndexError, ValueError):
                            pass
        except Exception as e:
            print(f"Failed to parse perf log: {e}")
            return {}
        
        if not frame_times:
            return {}
        
        return {
            "frame_time_avg": sum(frame_times) / len(frame_times),
            "frame_time_max": max(frame_times),
            "frame_time_p95": sorted(frame_times)[int(len(frame_times) * 0.95)] if frame_times else 0,
            "paint_time_avg": sum(paint_times) / len(paint_times) if paint_times else 0,
            "frame_samples": len(frame_times),
        }


def compare_versions(baseline_path: Path, current_path: Path, duration: int = 15) -> Dict:
    """Compare performance between two versions."""
    print("=" * 60)
    print("SRPSS Performance Comparison")
    print("=" * 60)
    
    results = {
        "baseline": {},
        "current": {},
        "comparison": {},
    }
    
    # Measure baseline (2.5)
    print(f"\n[1/2] Measuring BASELINE: {baseline_path.name}")
    print("-" * 60)
    baseline = PerformanceMeasurement(baseline_path, duration)
    if baseline.start_app():
        results["baseline"]["runtime"] = baseline.measure()
        baseline.stop_app()
        time.sleep(2)  # Cool down
        results["baseline"]["logs"] = baseline.parse_perf_log()
    else:
        print("FAILED to start baseline")
        return results
    
    # Measure current (2.6)
    print(f"\n[2/2] Measuring CURRENT: {current_path.name}")
    print("-" * 60)
    current = PerformanceMeasurement(current_path, duration)
    if current.start_app():
        results["current"]["runtime"] = current.measure()
        current.stop_app()
        time.sleep(2)
        results["current"]["logs"] = current.parse_perf_log()
    else:
        print("FAILED to start current")
        return results
    
    # Calculate comparison
    baseline_cpu = results["baseline"]["runtime"].get("cpu_avg", 0)
    current_cpu = results["current"]["runtime"].get("cpu_avg", 0)
    
    if baseline_cpu > 0:
        cpu_regression = ((current_cpu - baseline_cpu) / baseline_cpu) * 100
        results["comparison"]["cpu_regression_pct"] = cpu_regression
    
    baseline_mem = results["baseline"]["runtime"].get("memory_avg_mb", 0)
    current_mem = results["current"]["runtime"].get("memory_avg_mb", 0)
    
    if baseline_mem > 0:
        mem_regression = ((current_mem - baseline_mem) / baseline_mem) * 100
        results["comparison"]["memory_regression_pct"] = mem_regression
    
    baseline_frame = results["baseline"]["logs"].get("frame_time_avg", 0)
    current_frame = results["current"]["logs"].get("frame_time_avg", 0)
    
    if baseline_frame > 0:
        frame_regression = ((current_frame - baseline_frame) / baseline_frame) * 100
        results["comparison"]["frame_time_regression_pct"] = frame_regression
    
    return results


def print_results(results: Dict):
    """Print formatted results."""
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    baseline = results.get("baseline", {})
    current = results.get("current", {})
    comparison = results.get("comparison", {})
    
    # Runtime metrics
    print("\n[CPU Usage]")
    b_cpu = baseline.get("runtime", {})
    c_cpu = current.get("runtime", {})
    
    print(f"  Baseline: avg={b_cpu.get('cpu_avg', 0):.2f}% "
          f"min={b_cpu.get('cpu_min', 0):.2f}% "
          f"max={b_cpu.get('cpu_max', 0):.2f}% "
          f"p95={b_cpu.get('cpu_p95', 0):.2f}%")
    
    print(f"  Current:  avg={c_cpu.get('cpu_avg', 0):.2f}% "
          f"min={c_cpu.get('cpu_min', 0):.2f}% "
          f"max={c_cpu.get('cpu_max', 0):.2f}% "
          f"p95={c_cpu.get('cpu_p95', 0):.2f}%")
    
    cpu_reg = comparison.get("cpu_regression_pct", 0)
    status = "REGRESSION" if cpu_reg > 10 else "OK"
    print(f"  Regression: {cpu_reg:+.1f}% [{status}]")
    
    # Memory
    print("\n[Memory Usage]")
    print(f"  Baseline: avg={b_cpu.get('memory_avg_mb', 0):.1f}MB "
          f"max={b_cpu.get('memory_max_mb', 0):.1f}MB")
    print(f"  Current:  avg={c_cpu.get('memory_avg_mb', 0):.1f}MB "
          f"max={c_cpu.get('memory_max_mb', 0):.1f}MB")
    
    mem_reg = comparison.get("memory_regression_pct", 0)
    status = "REGRESSION" if mem_reg > 10 else "OK"
    print(f"  Regression: {mem_reg:+.1f}% [{status}]")
    
    # Frame timing
    print("\n[Frame Timing]")
    b_frame = baseline.get("logs", {})
    c_frame = current.get("logs", {})
    
    if b_frame and c_frame:
        print(f"  Baseline: avg={b_frame.get('frame_time_avg', 0):.2f}ms "
              f"max={b_frame.get('frame_time_max', 0):.2f}ms "
              f"p95={b_frame.get('frame_time_p95', 0):.2f}ms")
        print(f"  Current:  avg={c_frame.get('frame_time_avg', 0):.2f}ms "
              f"max={c_frame.get('frame_time_max', 0):.2f}ms "
              f"p95={c_frame.get('frame_time_p95', 0):.2f}ms")
        
        frame_reg = comparison.get("frame_time_regression_pct", 0)
        status = "REGRESSION" if frame_reg > 10 else "OK"
        print(f"  Regression: {frame_reg:+.1f}% [{status}]")
    else:
        print("  No frame timing data available")
    
    # Overall verdict
    print("\n" + "=" * 60)
    cpu_bad = cpu_reg > 10
    mem_bad = mem_reg > 10
    frame_bad = comparison.get("frame_time_regression_pct", 0) > 10
    
    if cpu_bad or mem_bad or frame_bad:
        print("VERDICT: PERFORMANCE REGRESSION DETECTED")
        if cpu_bad:
            print(f"  - CPU usage increased by {cpu_reg:.1f}%")
        if mem_bad:
            print(f"  - Memory usage increased by {mem_reg:.1f}%")
        if frame_bad:
            print(f"  - Frame time increased by {comparison.get('frame_time_regression_pct', 0):.1f}%")
    else:
        print("VERDICT: PERFORMANCE ACCEPTABLE")
    
    print("=" * 60)


def main():
    """Main entry point."""
    # Paths
    base_dir = Path(__file__).parent.parent.parent
    baseline_path = base_dir / "ShittyRandomPhotoScreenSaver2_5"
    current_path = base_dir / "ShittyRandomPhotoScreenSaver"
    
    if not baseline_path.exists():
        print(f"ERROR: Baseline path not found: {baseline_path}")
        return 1
    
    if not current_path.exists():
        print(f"ERROR: Current path not found: {current_path}")
        return 1
    
    # Run comparison
    results = compare_versions(baseline_path, current_path, duration=15)
    
    # Print results
    print_results(results)
    
    # Save results
    output_path = Path(__file__).parent / "perf_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")
    
    # Return exit code based on verdict
    comparison = results.get("comparison", {})
    cpu_reg = comparison.get("cpu_regression_pct", 0)
    mem_reg = comparison.get("memory_regression_pct", 0)
    frame_reg = comparison.get("frame_time_regression_pct", 0)
    
    if cpu_reg > 10 or mem_reg > 10 or frame_reg > 10:
        return 1  # Regression detected
    return 0  # OK


if __name__ == "__main__":
    sys.exit(main())
