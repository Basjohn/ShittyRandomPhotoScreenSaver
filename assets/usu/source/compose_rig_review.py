from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "renders" / "rig_validation"
OUT = SOURCE
VIEWS = ("front", "side", "back", "three_quarter", "high_rear", "high_side")
POSES = sorted(p.name for p in SOURCE.iterdir() if p.is_dir() and p.name != "collapsed_candidate" and all((p / f"{v}.png").is_file() for v in VIEWS))

def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()

def sheet(items, columns, tile_w, tile_h, title, dest):
    title_h, label_h = 54, 34
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * tile_w, title_h + rows * (tile_h + label_h)), (242, 242, 242))
    draw = ImageDraw.Draw(canvas)
    draw.text((14, 12), title, fill=(25, 25, 25), font=font(26))
    for i, (label, path) in enumerate(items):
        col, row = i % columns, i // columns
        x, y = col * tile_w, title_h + row * (tile_h + label_h)
        draw.rectangle((x, y, x + tile_w - 1, y + tile_h + label_h - 1), outline=(185, 185, 185), width=1)
        draw.text((x + 9, y + 6), label, fill=(20, 20, 20), font=font(20))
        with Image.open(path) as src:
            fitted = ImageOps.contain(src.convert("RGB"), (tile_w - 12, tile_h - 44), method=Image.Resampling.LANCZOS)
        canvas.paste(fitted, (x + (tile_w - fitted.width)//2, y + 38 + (tile_h - 38 - fitted.height)//2))
    canvas.save(dest, quality=95)
    return dest

for pose in POSES:
    items = [(view.replace("_", " ").upper(), SOURCE / pose / f"{view}.png") for view in VIEWS]
    sheet(items, 3, 480, 460, f"{pose.upper()} — six validation angles", OUT / f"review_{pose}_6view.jpg")

matrix_views = ("front", "side", "three_quarter", "high_rear")
items = [(f"{pose.upper()} · {view.replace('_',' ').upper()}", SOURCE / pose / f"{view}.png") for pose in POSES for view in matrix_views]
sheet(items, 4, 360, 390, "RIG POSE MATRIX — FRONT / SIDE / 3/4 / HIGH REAR", OUT / "review_pose_matrix.jpg")

items = [(f"{pose.upper()} · {view.replace('_',' ').upper()}", SOURCE / pose / f"{view}.png") for pose in ("neutral","ears_backward") for view in ("side","high_rear","three_quarter") if (SOURCE / pose / f"{view}.png").is_file()]
sheet(items, 3, 480, 480, "EAR BACKWARD vs NEUTRAL — ROOT / SKULL CHECK", OUT / "review_ears_backward_vs_neutral.jpg")

print(f"poses={len(POSES)}")
for pose in POSES:
    print(OUT / f"review_{pose}_6view.jpg")
print(OUT / "review_pose_matrix.jpg")
print(OUT / "review_ears_backward_vs_neutral.jpg")

# Motion contact sheets and synchronized action-comparison GIFs. The render
# set contains every other source frame; 24 fps source timing therefore maps
# to a 12 fps GIF by showing each rendered frame once.
MOTION = SOURCE / "motion_frames"
actions = ("rest", "walk", "run", "ears")
motion_views = ("side", "three_quarter")

def numbered_frames(action, view):
    folder = MOTION / action / view
    def frame_number(path):
        match = re.fullmatch(r"(\d+)\.png", path.name)
        return int(match.group(1)) if match else -1
    return sorted((p for p in folder.glob("*.png") if frame_number(p) >= 0), key=frame_number)

def motion_contact(action):
    frames = {view: numbered_frames(action, view) for view in motion_views}
    usable = min((len(v) for v in frames.values()), default=0)
    if not usable:
        return
    picks = sorted(set((0, usable // 4, usable // 2, 3 * usable // 4, usable - 1)))
    items = []
    for view in motion_views:
        for i in picks:
            items.append((f"{view.upper()} · frame {frames[view][i].stem}", frames[view][i]))
    sheet(items, 5, 360, 430, f"{action.upper()} — SIDE / THREE-QUARTER MOTION SAMPLES", OUT / f"review_motion_{action}.jpg")

def comparison_gif(view):
    sequences = {action: numbered_frames(action, view) for action in actions}
    sequences = {name: seq for name, seq in sequences.items() if seq}
    if not sequences:
        return
    count = max(len(seq) for seq in sequences.values())
    tile_w, tile_h, label_h = 480, 480, 38
    font_label = font(21)
    rendered = []
    for t in range(count):
        canvas = Image.new("RGB", (tile_w * 2, (tile_h + label_h) * 2), (242, 242, 242))
        draw = ImageDraw.Draw(canvas)
        for i, action in enumerate(actions):
            seq = sequences.get(action)
            if not seq:
                continue
            idx = round(t * (len(seq) - 1) / max(1, count - 1))
            with Image.open(seq[idx]) as src:
                fitted = ImageOps.contain(src.convert("RGB"), (tile_w - 12, tile_h - 48), method=Image.Resampling.LANCZOS)
            col, row = i % 2, i // 2
            x, y = col * tile_w, row * (tile_h + label_h)
            draw.rectangle((x, y, x + tile_w - 1, y + tile_h + label_h - 1), outline=(185, 185, 185), width=1)
            draw.text((x + 10, y + 7), f"{action.upper()} · {seq[idx].stem}", fill=(20, 20, 20), font=font_label)
            canvas.paste(fitted, (x + (tile_w - fitted.width)//2, y + 39 + (tile_h - 39 - fitted.height)//2))
        rendered.append(canvas)
    target = OUT / f"review_motion_comparison_{view}.gif"
    # GIF stores delays in 10 ms units, so 83.33 ms cannot be represented on
    # every frame. An 80/80/90 ms cadence averages 83.33 ms (12 fps).
    durations = [80 if i % 3 in (0, 1) else 90 for i in range(len(rendered))]
    rendered[0].save(target, save_all=True, append_images=rendered[1:], duration=durations, loop=0, optimize=False)
    print(target)

for action in actions:
    motion_contact(action)
comparison_gif("side")
comparison_gif("three_quarter")

# Explicit intermediate pair checks avoid judging a closed loop by comparing
# only its matching first and final poses.
for view in motion_views:
    items = []
    for action in ("walk", "run"):
        for first, second in ((3, 13), (7, 19)):
            for frame in (first, second):
                path = MOTION / action / view / f"{frame:03}.png"
                if path.is_file():
                    items.append((f"{action.upper()} · {view.upper()} · {frame:03}", path))
    if items:
        sheet(items, 4, 420, 480, f"MOTION INTERMEDIATE PAIRS — {view.upper()}", OUT / f"review_motion_intermediate_{view}.jpg")
