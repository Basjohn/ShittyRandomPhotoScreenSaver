"""Performance baseline test - Run app for 15s and analyze metrics.

Usage:
    $env:SRPSS_PERF_METRICS = '1'
    python tests/perf_baseline_test.py
"""
import subprocess
import time
import sys
import os
from pathlib import Path

def run_perf_test(duration_seconds=15):
    """Run the app for specified duration and capture performance metrics."""
    
    # Set environment variables
    env = os.environ.copy()
    env['SRPSS_PERF_METRICS'] = '1'
    
    print(f"Starting performance test ({duration_seconds}s)...")
    print("Environment: SRPSS_PERF_METRICS=1")
    
    # Start the application
    proc = subprocess.Popen(
        ['python', 'main.py', '--debug'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    try:
        # Wait for specified duration
        time.sleep(duration_seconds)
        
        # Terminate the process
        print(f"\nTerminating after {duration_seconds}s...")
        proc.terminate()
        
        # Wait for clean shutdown (max 5s)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Force killing process...")
            proc.kill()
            proc.wait()
        
        print("Process terminated")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user, terminating...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    
    return proc.returncode

def analyze_logs():
    """Analyze performance logs and extract key metrics."""
    
    log_dir = Path(__file__).parent.parent / 'logs'
    perf_log = log_dir / 'screensaver_perf.log'
    vis_log = log_dir / 'screensaver_spotify_vis.log'
    main_log = log_dir / 'screensaver.log'
    
    print("\n" + "="*80)
    print("PERFORMANCE ANALYSIS")
    print("="*80)
    
    # Analyze frame spikes
    if perf_log.exists():
        print("\n--- Frame Budget Analysis ---")
        with open(perf_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        spike_count = 0
        max_spike = 0.0
        for line in lines[-200:]:  # Last 200 lines
            if 'Frame spike:' in line:
                spike_count += 1
                try:
                    # Extract spike time: "Frame spike: 41.1ms"
                    parts = line.split('Frame spike:')[1].split('ms')[0].strip()
                    spike_ms = float(parts)
                    max_spike = max(max_spike, spike_ms)
                except:
                    pass
        
        print(f"Frame spikes detected: {spike_count}")
        print(f"Max frame spike: {max_spike:.1f}ms")
        print(f"Target frame time: 16.7ms (60 FPS)")
        print(f"Spike severity: {max_spike / 16.7:.1f}x over budget")
    
    # Analyze visualizer performance
    if vis_log.exists():
        print("\n--- Visualizer Performance ---")
        with open(vis_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines[-50:]:  # Last 50 lines
            if 'Tick metrics:' in line and 'avg_fps' in line:
                print(f"Visualizer: {line.split('Tick metrics:')[1].strip()}")
                break
    
    # Analyze transition performance
    if perf_log.exists():
        print("\n--- Transition Performance ---")
        with open(perf_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines[-100:]:
            if '[GL COMPOSITOR]' in line and 'metrics:' in line:
                transition_name = line.split('[GL COMPOSITOR]')[1].split('metrics:')[0].strip()
                metrics = line.split('metrics:')[1].strip()
                print(f"{transition_name}: {metrics}")
    
    # Analyze slow operations
    if perf_log.exists():
        print("\n--- Slow Operations (>20ms) ---")
        with open(perf_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        slow_ops = []
        for line in lines[-200:]:
            if 'Slow' in line or 'slow' in line:
                slow_ops.append(line.strip())
        
        if slow_ops:
            for op in slow_ops[-10:]:  # Last 10 slow operations
                print(f"  {op}")
        else:
            print("  No slow operations detected")
    
    # Analyze texture uploads
    if perf_log.exists():
        print("\n--- Texture Upload Performance ---")
        with open(perf_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        upload_count = 0
        total_upload_time = 0.0
        max_upload_time = 0.0
        
        for line in lines[-200:]:
            if '[GL TEXTURE] Slow upload:' in line:
                upload_count += 1
                try:
                    # Extract upload time: "Slow upload: 25.3ms"
                    parts = line.split('Slow upload:')[1].split('ms')[0].strip()
                    upload_ms = float(parts)
                    total_upload_time += upload_ms
                    max_upload_time = max(max_upload_time, upload_ms)
                except:
                    pass
        
        if upload_count > 0:
            avg_upload_time = total_upload_time / upload_count
            print(f"Slow uploads detected: {upload_count}")
            print(f"Average upload time: {avg_upload_time:.1f}ms")
            print(f"Max upload time: {max_upload_time:.1f}ms")
        else:
            print("No slow texture uploads detected")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    # Generate recommendations based on findings
    recommendations = []
    
    if spike_count > 10:
        recommendations.append("- High frame spike count: Investigate GC coordination and frame budget usage")
    
    if max_spike > 40.0:
        recommendations.append("- Severe frame spikes: Check for blocking operations on UI thread")
    
    if upload_count > 5:
        recommendations.append("- Frequent slow texture uploads: Optimize image conversion or add texture caching")
    
    if not recommendations:
        recommendations.append("- Performance appears acceptable, but check FPS targets")
    
    for rec in recommendations:
        print(rec)
    
    print("\n" + "="*80)

if __name__ == '__main__':
    duration = 15
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, using default 15s")
    
    returncode = run_perf_test(duration)
    analyze_logs()
    
    sys.exit(returncode if returncode else 0)
