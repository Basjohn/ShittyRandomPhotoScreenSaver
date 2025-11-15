# 3D Puzzle-Flip Transition — Design Notes & Implementation

## Summary
This document explains how to create screen tiles that are puzzle-shaped, flip in 3D, and have a glassy reflective rim using three cooperating layers:

- **Geometry** — small 3D quads (two triangles each) rotated per-block.
- **Shape** — puzzle silhouette applied via an alpha mask per block.
- **Material** — Fresnel-based rim lighting shader for glass effect.

---

## 1. Geometry (3D Rotation via GL Quads)

Each block becomes a 3D plane that rotates around its Y-axis.

**Steps:**  
1. Create a rectangular quad (two triangles) per block.  
2. Assign two textures per block: one for the *old image section* (front) and one for the *new* (back).  
3. Rotate each quad using:
   ```
   angle = (1 - flip_progress) * 180°
   ```
4. If `angle < 90°`: draw the front texture; otherwise draw the back.

**Example:**
```python
glBindTexture(GL_TEXTURE_2D, block.front_tex if angle < 90 else block.back_tex)
glUniformMatrix4fv(u_model, 1, GL_FALSE, model_matrix)
glDrawArrays(GL_TRIANGLES, 0, 6)
```

---

## 2. Shape (Puzzle-Piece Alpha Masks)

### Purpose
To give each quad a non-rectangular puzzle silhouette.

### Options
- **Alpha Texture Mask (Recommended)** — Pre-generate a mask for each block using QPainter or Pillow, store transparency in alpha channel, and multiply with texture alpha in shader.
- **Procedural Geometry (Harder)** — Directly create puzzle-shaped meshes.

### Key Notes
- Adjacent edges must match: if the right edge of one block has a tab, the left edge of the next must have a slot.
- Cache generated masks for performance.

---

## 3. Material (Fresnel Rim Shader)

Adds a reflective glass-like rim to blocks.

### Fragment Shader
```glsl
#version 330
in vec3 vNormal;
in vec2 vUV;
uniform sampler2D tex;
uniform sampler2D mask;
uniform vec3 viewDir;
uniform float fresnelPower;
out vec4 fragColor;

void main() {
    vec3 n = normalize(vNormal);
    float f = pow(1.0 - max(dot(n, viewDir), 0.0), fresnelPower);
    vec4 base = texture(tex, vUV);
    float alpha = texture(mask, vUV).a;
    vec3 rim = vec3(1.0) * f * 0.3;
    fragColor = vec4(base.rgb + rim, base.a * alpha);
}
```

### Vertex Shader
```glsl
#version 330
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUV;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec3 vNormal;
out vec2 vUV;

void main() {
    vNormal = mat3(model) * aNormal;
    vUV = aUV;
    gl_Position = projection * view * model * vec4(aPos, 1.0);
}
```

### Tuning Parameters
- **fresnelPower:** 2–6 for subtle → strong reflections.
- Rim color multiplier: adjust the constant `0.3` for brightness.
- Add cube-mapped reflections later for realism.

---

## 4. Integration Steps

1. **Preprocessing:**
   - Split screen into randomized-size blocks.
   - For each block: extract old/new textures and generate puzzle mask.

2. **Initialize GL:**
   - Compile vertex + fragment shaders.
   - Create VAO/VBO for a unit quad.

3. **Animation Loop:**
   - Compute rotation angle from transition progress.
   - Bind front/back textures and mask.
   - Draw quad with shader.

4. **Completion:**
   - When all rotations hit 180°, swap front/back images for the next frame.

---

## 5. Performance Notes

- Reuse textures and masks between transitions.
- Limit total blocks to ~100–200.
- Use depth testing and back-face culling.
- Use instanced rendering if performance becomes critical.

---

## 6. Dependencies

- No downloads required — shaders compile from text strings.  
- Works with PySide6 (QOpenGLWidget) or PyOpenGL.  
- Example load code:
  ```python
  program.addShaderFromSourceCode(QOpenGLShader.Vertex, vertex_shader_src)
  program.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment_shader_src)
  program.link()
  ```

---

## 7. Modified Python Transition File (Random Sizes + Puzzle Masks)

```python
import math
import random
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QOpenGLWidget


def make_puzzle_mask(w: int, h: int, tabs=(0, 0, 0, 0)) -> QImage:
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    margin = min(w, h) * 0.12
    path.addRect(0, 0, w, h)
    p.fillPath(path, QColor(255, 255, 255, 255))
    p.end()
    return img


class _GLFlipBlock:
    def __init__(self, rect: QRect):
        self.rect = rect
        self.flip_progress = 0.0


class _GLBlockFlipWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._old = None
        self._composite_pixmap = None

    def set_old(self, pixmap: QPixmap):
        self._old = pixmap
        self.update()

    def set_region_pixmap(self, pixmap: QPixmap):
        self._composite_pixmap = pixmap
        self.update()

    def paintGL(self):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            target = self.rect()
            if self._old and not self._old.isNull():
                p.drawPixmap(target, self._old)
            if self._composite_pixmap:
                p.drawPixmap(0, 0, self._composite_pixmap)
        finally:
            p.end()


class BlockFlipTransition:
    def __init__(self, gl_widget: _GLBlockFlipWidget):
        self._gl = gl_widget
        self._blocks = []
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._on_anim_update)
        self._grid_cols = 8
        self._progress = 0.0
        self._new = None

    def _create_block_grid(self, width: int, height: int) -> None:
        self._blocks = []
        base_cols = self._grid_cols * 2
        aspect_ratio = height / max(1, width)
        calculated_rows = max(2, int(round(base_cols * aspect_ratio)))
        effective_rows = calculated_rows
        effective_cols = base_cols
        base_w = max(1, width // effective_cols)
        base_h = max(1, height // effective_rows)
        jitter = 0.35

        x = 0
        col_widths = []
        for c in range(effective_cols):
            if c == effective_cols - 1:
                w = width - x
            else:
                delta = int(base_w * jitter * (random.random() * 2 - 1))
                w = max(1, base_w + delta)
                if x + w > width - (effective_cols - c - 1):
                    w = max(1, width - x - (effective_cols - c - 1))
            col_widths.append(w)
            x += w

        y = 0
        row_heights = []
        for r in range(effective_rows):
            if r == effective_rows - 1:
                h = height - y
            else:
                delta = int(base_h * jitter * (random.random() * 2 - 1))
                h = max(1, base_h + delta)
                if y + h > height - (effective_rows - r - 1):
                    h = max(1, height - y - (effective_rows - r - 1))
            row_heights.append(h)
            y += h

        y = 0
        for row in range(effective_rows):
            x = 0
            h = row_heights[row]
            for col in range(effective_cols):
                w = col_widths[col]
                self._blocks.append(_GLFlipBlock(QRect(x, y, w, h)))
                x += w
            y += h

    def start(self, old_pixmap: QPixmap, new_pixmap: QPixmap):
        self._gl.set_old(old_pixmap)
        self._new = new_pixmap
        self._create_block_grid(self._gl.width(), self._gl.height())
        for b in self._blocks:
            b.flip_progress = 0.0
        self._progress = 0.0
        self._anim_timer.start(16)

    def _on_anim_update(self):
        self._progress += 0.02
        if self._progress >= 1.0:
            self._progress = 1.0
            self._anim_timer.stop()

        composite = QPixmap(self._gl.width(), self._gl.height())
        composite.fill(Qt.transparent)
        tmp_p = QPainter(composite)
        tmp_p.setRenderHint(QPainter.Antialiasing, True)

        for block in self._blocks:
            pval = self._progress
            if pval <= 0:
                continue
            r = block.rect
            reveal_w = max(1, int(r.width() * pval))
            dx = r.x() + (r.width() - reveal_w) // 2
            src = self._new.copy(
                r.x() + (r.width() - reveal_w) // 2, r.y(), reveal_w, r.height()
            )
            mask_img = make_puzzle_mask(r.width(), r.height())
            mask_pix = QPixmap.fromImage(mask_img)
            if reveal_w != r.width():
                mask_pix = mask_pix.copy(
                    (r.width() - reveal_w) // 2, 0, reveal_w, r.height()
                )
            src.setMask(mask_pix.createMaskFromColor(QColor(0, 0, 0, 0).rgba()))
            tmp_p.drawPixmap(dx, r.y(), src)

        tmp_p.end()
        self._gl.set_region_pixmap(composite)
```
