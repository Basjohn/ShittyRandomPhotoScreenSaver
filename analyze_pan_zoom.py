"""Analyze pan & scan zoom issues from logs."""
import re

with open('logs/screensaver.log', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all "Scaled for pan" lines
pan_lines = []
for i, line in enumerate(lines):
    if 'Scaled for pan:' in line:
        pan_lines.append((i+1, line.strip()))

# Also track which screen
screen_lines = []
for i, line in enumerate(lines):
    if 'Image displayed on screen' in line:
        screen_lines.append((i+1, line.strip()))

print("=== PAN & SCAN SCALING (Last 30) ===")
for line_num, line in pan_lines[-30:]:
    print(f"{line_num}: {line}")

print("\n=== SCREEN ASSIGNMENTS (Last 30) ===")
for line_num, line in screen_lines[-30:]:
    print(f"{line_num}: {line}")

# Analyze zoom pattern on same screen
print("\n=== ZOOM ANALYSIS ===")
screen_0_scales = []
screen_1_scales = []

for i in range(len(pan_lines)):
    line_num, pan_line = pan_lines[i]
    
    # Find next screen assignment after this pan line
    for screen_num, screen_line in screen_lines:
        if screen_num > line_num:
            # Extract dimensions
            match = re.search(r'(\d+)x(\d+) → (\d+)x(\d+)', pan_line)
            if match:
                orig_w, orig_h, scaled_w, scaled_h = map(int, match.groups())
                
                if 'screen 0:' in screen_line:
                    screen_0_scales.append((orig_w, orig_h, scaled_w, scaled_h))
                elif 'screen 1:' in screen_line:
                    screen_1_scales.append((orig_w, orig_h, scaled_w, scaled_h))
            break

print(f"\nScreen 0 scales (last 10): {screen_0_scales[-10:]}")
print(f"\nScreen 1 scales (last 10): {screen_1_scales[-10:]}")

# Check for zoom (same input, different output)
print("\n=== ZOOM DETECTION ===")
for i in range(1, len(screen_0_scales)):
    prev = screen_0_scales[i-1]
    curr = screen_0_scales[i]
    if prev[0:2] == curr[0:2] and prev[2:4] != curr[2:4]:
        print(f"Screen 0 ZOOM: {prev[0]}x{prev[1]} → {prev[2]}x{prev[3]} THEN → {curr[2]}x{curr[3]}")

for i in range(1, len(screen_1_scales)):
    prev = screen_1_scales[i-1]
    curr = screen_1_scales[i]
    if prev[0:2] == curr[0:2] and prev[2:4] != curr[2:4]:
        print(f"Screen 1 ZOOM: {prev[0]}x{prev[1]} → {prev[2]}x{prev[3]} THEN → {curr[2]}x{curr[3]}")
