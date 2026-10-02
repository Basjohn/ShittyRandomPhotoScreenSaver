# R-102 — Frozen Qt Quick Runtime Pruned The PySide6.QtOpenGL Binding

**Status:** SOLVED (2026-10-02). Frozen runtime/build contracts now retain the Qt OpenGL binding required by Qt Quick while the genuinely unused OpenGLWidgets layer remains pruned.

## Symptom

After aggressive frozen-package debloating, ordinary and Diagnostic frozen products could fail before useful application logging. Source code did not directly import `PySide6.QtOpenGL`, which made the module look removable during a source-oriented fossil sweep.

## Root cause

Application-source imports were the wrong authority for this dependency. The frozen Qt Quick runtime requires the **PySide6 binding-level QtOpenGL module/native substrate** even though SRPSS application code does not name it directly. Removing that binding broke the frozen import/runtime graph. `Qt6OpenGLWidgets` is a separate QWidget-era dependency and remains unused.

## Fix / durable bar

- Every runtime freeze explicitly retains `PySide6.QtOpenGL` and its native binding/substrate.
- The prune/denylist may not remove that dependency merely because source grep finds no direct import.
- `Qt6OpenGLWidgets` remains pruned; retaining QtOpenGL is not permission to restore QWidget/QOpenGLWidget runtime architecture.
- Build-layout tests own the distinction.

## Lesson

Frozen dependency pruning follows the **actual frozen import/runtime graph**, not just application-source imports. Likewise, modern GL/ARB/KHR capability should not be stripped merely because its first planned 3D consumer has not landed yet.
