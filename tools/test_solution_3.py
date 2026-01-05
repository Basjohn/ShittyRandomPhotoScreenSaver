"""Test script for Solution 3 implementation.

Measures dt_max and frame timing before/after worker offloading fixes.
"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def parse_perf_log(log_path: Path) -> dict:
    """Parse performance metrics from log file."""
    metrics = {
        'dt_max_values': [],
        'avg_fps_values': [],
        'spike_counts': [],
    }
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '[GL ANIM] Slide metrics:' in line:
                # Extract dt_max
                if 'dt_max=' in line:
                    try:
                        dt_str = line.split('dt_max=')[1].split('ms')[0]
                        metrics['dt_max_values'].append(float(dt_str))
                    except:
                        pass
                
                # Extract avg_fps
                if 'avg_fps=' in line:
                    try:
                        fps_str = line.split('avg_fps=')[1].split(',')[0]
                        metrics['avg_fps_values'].append(float(fps_str))
                    except:
                        pass
                
                # Extract spikes
                if 'spikes=' in line:
                    try:
                        spike_str = line.split('spikes=')[1].split(',')[0]
                        metrics['spike_counts'].append(int(spike_str))
                    except:
                        pass
    
    return metrics

def calculate_stats(values: list) -> dict:
    """Calculate statistics from list of values."""
    if not values:
        return {'min': 0, 'max': 0, 'mean': 0, 'count': 0}
    
    return {
        'min': min(values),
        'max': max(values),
        'mean': sum(values) / len(values),
        'count': len(values),
    }

def main():
    """Run performance test and analyze results."""
    print("=" * 80)
    print("Solution 3 Performance Test")
    print("=" * 80)
    print()
    
    log_path = Path(__file__).parent.parent / "logs" / "screensaver_perf.log"
    
    if not log_path.exists():
        print(f"ERROR: Log file not found: {log_path}")
        print("Run the screensaver with SRPSS_PERF_METRICS=1 first")
        return 1
    
    print(f"Analyzing: {log_path}")
    print()
    
    metrics = parse_perf_log(log_path)
    
    # Calculate statistics
    dt_max_stats = calculate_stats(metrics['dt_max_values'])
    fps_stats = calculate_stats(metrics['avg_fps_values'])
    spike_stats = calculate_stats(metrics['spike_counts'])
    
    print("Performance Metrics")
    print("-" * 80)
    print(f"Transitions analyzed: {dt_max_stats['count']}")
    print()
    
    print("dt_max (frame time):")
    print(f"  Min:  {dt_max_stats['min']:.2f}ms")
    print(f"  Max:  {dt_max_stats['max']:.2f}ms")
    print(f"  Mean: {dt_max_stats['mean']:.2f}ms")
    print(f"  Target: <20ms")
    status = '✅ PASS' if dt_max_stats['mean'] < 20 else '🔴 FAIL'
    print(f"  Status: {status}")
    print()
    
    print("avg_fps:")
    print(f"  Min:  {fps_stats['min']:.1f}")
    print(f"  Max:  {fps_stats['max']:.1f}")
    print(f"  Mean: {fps_stats['mean']:.1f}")
    print(f"  Target: 58-60")
    status = '✅ PASS' if fps_stats['mean'] >= 58 else '🔴 FAIL'
    print(f"  Status: {status}")
    print()
    
    print("Spikes per transition:")
    print(f"  Min:  {spike_stats['min']}")
    print(f"  Max:  {spike_stats['max']}")
    print(f"  Mean: {spike_stats['mean']:.1f}")
    print(f"  Target: 0")
    status = '✅ PASS' if spike_stats['mean'] == 0 else '🔴 FAIL'
    print(f"  Status: {status}")
    print()
    
    # Overall assessment
    print("=" * 80)
    if dt_max_stats['mean'] < 20 and fps_stats['mean'] >= 58:
        print("✅ PERFORMANCE TARGET MET")
    elif dt_max_stats['mean'] < 30 and fps_stats['mean'] >= 50:
        print("🟡 IMPROVED BUT NOT AT TARGET")
    else:
        print("🔴 PERFORMANCE TARGET NOT MET")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
