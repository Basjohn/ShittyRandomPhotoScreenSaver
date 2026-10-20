"""Render only Extruded Bubble's Guided Setup preview through the foundry's own path (the other previews stay)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import Image
from tools import onboarding_preview_foundry as foundry, onboarding_sheet_previews

width, height = foundry._RENDERED_PREVIEW_SIZE
scratch = ROOT / "tmp" / "eb_s4" / "extruded_bubble_bars.png"
foundry._render_spectrum_preview(scratch, width=width, height=height, mode="extruded_bubble")
backdrop = Image.new("RGBA", (width, height))
for row in range(height):
    shade = int(16 + 20 * row / max(1, height - 1))
    backdrop.paste((shade, shade + 2, shade + 8, 255), (0, row, width, row + 1))
with Image.open(scratch) as bars:
    backdrop.alpha_composite(bars.convert("RGBA"))
framed = onboarding_sheet_previews._framed(backdrop, (255, 255, 255))
foundry.save_png_stable(onboarding_sheet_previews._with_shadow(framed), foundry.DEFAULT_OUTPUT / "visualizer_extruded_bubble.png")
print("ok")
