#!/usr/bin/env python3
"""SRPSS Theme Foundry.

A deliberately narrow developer utility for authoring the colours/opacity of:

* the SRPSS Settings GUI; and
* the screensaver context menu.

It does NOT discover or edit runtime widget appearance, visualizer colours,
transition rendering, overlays, cursor halo, or other screensaver presentation.

The tool edits the existing canonical presentation sources rather than creating a
second runtime theme authority.  Theme files (``.srtheme``) are full snapshots of
EVERY token exposed by the tool, including unchanged values and link metadata.
That makes files authored today suitable for a future selectable-theme system
without making Theme Foundry a runtime theme manager now.

Typical repository location::

    tools/theme_foundry.py

Run::

    python tools/theme_foundry.py

or, if the script lives elsewhere::

    python theme_foundry.py --repo X:\\path\\to\\ShittyRandomPhotoScreenSaver

Safety model
------------
* Only an explicit allow-list of Settings/context-menu source files is scanned.
* Apply refuses to overwrite a source file that changed externally after reload.
* All edits are prepared in memory before any file is replaced.
* Atomic writes are used; no persistent backup/helper files are created.
* Git HEAD is read-only and serves as the repository-default comparison/revert
  source when available.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


APP_TITLE = "SRPSS Theme Foundry"
THEME_FORMAT = "srpss-theme"
THEME_VERSION = 1
THEME_EXTENSION = ".srtheme"
PREFERENCES_VERSION = 1
DIAGNOSTIC_QSS_PATH = "themes/dark.qss"


# Intentionally narrow.  Do not add runtime widget/rendering sources here merely
# because they contain colours.  Theme Foundry's durable scope is Settings GUI +
# screensaver context menu unless the operator explicitly expands it.
SOURCE_ROLES: tuple[tuple[str, str, str], ...] = (
    ("ui/settings_theme.py", "settings_theme", "Settings Theme"),
    ("ui/tabs/shared_styles.py", "shared_styles", "Settings Controls"),
    ("ui/settings_dialog.py", "settings_dialog", "Settings Chrome"),
    ("ui/settings_about_tab.py", "settings_about", "Settings About"),
    ("core/windows/dwm_blur.py", "dwm", "Settings Acrylic"),
    ("widgets/context_menu.py", "context_menu", "Context Menu"),
)

# Python string assignments that are safe presentation-only theme sources.
STYLE_ASSIGNMENT_ALLOWLIST: dict[str, Callable[[str], bool]] = {
    "ui/settings_theme.py": lambda name: name == "custom_styles",
    "ui/tabs/shared_styles.py": lambda name: "STYLE" in name.upper(),
    "widgets/context_menu.py": lambda name: name in {"MENU_STYLE", "SUBMENU_STYLE"},
}

# These settings-only files may safely expose literal CSS colours found in any
# Python string.  This captures local popup/card styling without turning the
# scanner loose on the rest of the project.
GENERIC_STRING_COLOR_FILES = {
    "ui/settings_dialog.py",
    "ui/settings_about_tab.py",
}

# QColor calls in these files are presentation colours (shadows, shell chrome,
# local cards/preview chrome).  We intentionally do not scan arbitrary ui/tabs
# QColor values because some tab code represents actual saved widget colour data.
QCOLOR_FILES = {
    "ui/settings_dialog.py",
    "ui/settings_about_tab.py",
    "ui/tabs/shared_styles.py",
}


RGBA_RE = re.compile(
    r"rgba\(\s*(?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})\s*,\s*(?P<a>\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)
RGB_RE = re.compile(
    r"rgb\(\s*(?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})\s*\)",
    re.IGNORECASE,
)
HEX_RE = re.compile(r"(?<![\w])#(?P<hex>[0-9a-fA-F]{6})(?![0-9a-fA-F])")
TRANSPARENT_RE = re.compile(r"\btransparent\b", re.IGNORECASE)
QCOLOR_RE = re.compile(
    r"QColor\(\s*(?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})(?:\s*,\s*(?P<a>\d{1,3}))?\s*\)"
)


@dataclass(frozen=True)
class Rgba:
    r: int
    g: int
    b: int
    a: int = 255

    def clamped(self) -> "Rgba":
        return Rgba(*(max(0, min(255, int(v))) for v in (self.r, self.g, self.b, self.a)))

    def to_qcolor(self) -> QColor:
        c = self.clamped()
        return QColor(c.r, c.g, c.b, c.a)

    def to_json(self) -> list[int]:
        c = self.clamped()
        return [c.r, c.g, c.b, c.a]

    @classmethod
    def from_json(cls, value: object) -> "Rgba":
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise ValueError("RGBA must be a four-item list")
        return cls(*(int(v) for v in value)).clamped()

    @property
    def hex_rgb(self) -> str:
        c = self.clamped()
        return f"#{c.r:02X}{c.g:02X}{c.b:02X}"

    @property
    def alpha_percent(self) -> float:
        return self.a * 100.0 / 255.0


@dataclass(frozen=True)
class Binding:
    """One exact source span updated when a token is applied."""

    source_path: str
    start: int
    end: int
    style: str
    channel: str | None = None

    def render(self, value: Rgba) -> str:
        c = value.clamped()
        if self.style == "rgba_int":
            return f"rgba({c.r}, {c.g}, {c.b}, {c.a})"
        if self.style == "rgba_float":
            alpha = c.a / 255.0
            text = f"{alpha:.3f}".rstrip("0").rstrip(".")
            if text == "1":
                text = "1.0"
            elif text == "0":
                text = "0.0"
            return f"rgba({c.r}, {c.g}, {c.b}, {text})"
        if self.style == "rgb":
            if c.a == 255:
                return f"rgb({c.r}, {c.g}, {c.b})"
            return f"rgba({c.r}, {c.g}, {c.b}, {c.a})"
        if self.style == "hex":
            if c.a == 255:
                return c.hex_rgb
            return f"rgba({c.r}, {c.g}, {c.b}, {c.a})"
        if self.style == "transparent":
            if c.a == 0 and c.r == 0 and c.g == 0 and c.b == 0:
                return "transparent"
            return f"rgba({c.r}, {c.g}, {c.b}, {c.a})"
        if self.style == "qcolor3":
            if c.a == 255:
                return f"QColor({c.r}, {c.g}, {c.b})"
            return f"QColor({c.r}, {c.g}, {c.b}, {c.a})"
        if self.style == "qcolor4":
            return f"QColor({c.r}, {c.g}, {c.b}, {c.a})"
        if self.style == "channel_int":
            if self.channel == "r":
                return str(c.r)
            if self.channel == "g":
                return str(c.g)
            if self.channel == "b":
                return str(c.b)
            if self.channel == "a":
                return str(c.a)
            raise ValueError(f"Unknown channel: {self.channel}")
        raise ValueError(f"Unsupported binding style: {self.style}")


@dataclass
class ThemeToken:
    token_id: str
    label: str
    category: str
    value: Rgba
    source_path: str
    source_hint: str
    bindings: list[Binding] = field(default_factory=list)
    default_link_group: str | None = None
    # Foundry-only metadata.  These do not become runtime theme authorities.
    description: str = ""

    @property
    def official_name(self) -> str:
        """Stable source identity shown alongside the friendlier Foundry label."""
        return self.token_id


@dataclass
class SourceSnapshot:
    text: str
    sha256: str


@dataclass
class DiscoveryResult:
    tokens: dict[str, ThemeToken]
    sources: dict[str, SourceSnapshot]
    warnings: list[str]
    # Read-only presentation sources that can explain layering/overrides but are
    # intentionally outside Theme Foundry's editable scope.
    diagnostic_sources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _StringAssignment:
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class _ContextRange:
    label: str
    start: int
    end: int
    depth: int


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer("\n", text):
        offsets.append(match.end())
    return offsets


def _abs_offset(offsets: list[int], line: int, col: int) -> int:
    return offsets[max(0, line - 1)] + col


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("::", "_").replace(":", "_").replace("#", "")
    value = value.replace("[", "_").replace("]", "_")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "token"


def _humanize(value: str) -> str:
    value = value.replace("::", " ").replace("#", "").replace("_", " ")
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.title() if value else "Colour"


def _parse_color_match(match: re.Match[str]) -> tuple[Rgba, str]:
    text = match.group(0)
    if match.re is RGBA_RE:
        r, g, b = (int(match.group(k)) for k in ("r", "g", "b"))
        a_text = match.group("a")
        if "." in a_text or float(a_text) <= 1.0:
            a = round(float(a_text) * 255.0)
            style = "rgba_float"
        else:
            a = int(float(a_text))
            style = "rgba_int"
        return Rgba(r, g, b, a).clamped(), style
    if match.re is RGB_RE:
        return Rgba(int(match.group("r")), int(match.group("g")), int(match.group("b")), 255), "rgb"
    if match.re is HEX_RE:
        h = match.group("hex")
        return Rgba(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255), "hex"
    if match.re is TRANSPARENT_RE:
        return Rgba(0, 0, 0, 0), "transparent"
    raise ValueError(f"Unsupported colour literal: {text}")


def _iter_color_matches(text: str) -> Iterable[tuple[re.Match[str], Rgba, str]]:
    matches: list[tuple[int, re.Match[str], Rgba, str]] = []
    for regex in (RGBA_RE, RGB_RE, HEX_RE, TRANSPARENT_RE):
        for match in regex.finditer(text):
            value, style = _parse_color_match(match)
            matches.append((match.start(), match, value, style))
    # Avoid HEX matches inside rgba text etc. by dropping overlapping spans.
    matches.sort(key=lambda item: (item[0], -(item[1].end() - item[1].start())))
    accepted: list[tuple[re.Match[str], Rgba, str]] = []
    occupied: list[tuple[int, int]] = []
    for _pos, match, value, style in matches:
        span = (match.start(), match.end())
        if any(not (span[1] <= a or span[0] >= b) for a, b in occupied):
            continue
        occupied.append(span)
        accepted.append((match, value, style))
    accepted.sort(key=lambda item: item[0].start())
    yield from accepted


def _assignment_ranges(source: str) -> list[_StringAssignment]:
    offsets = _line_offsets(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    assignments: list[_StringAssignment] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        name = None
        for target in targets:
            if isinstance(target, ast.Name):
                name = target.id
                break
        value_node = node.value
        if not name or value_node is None or not hasattr(value_node, "lineno") or not hasattr(value_node, "end_lineno"):
            continue
        start = _abs_offset(offsets, value_node.lineno, value_node.col_offset)
        end = _abs_offset(offsets, value_node.end_lineno, value_node.end_col_offset)
        assignments.append(_StringAssignment(name=name, start=start, end=end))
    return assignments


def _context_ranges(source: str) -> list[_ContextRange]:
    offsets = _line_offsets(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    ranges: list[_ContextRange] = []

    def walk(node: ast.AST, parents: list[str]) -> None:
        label = None
        if isinstance(node, ast.ClassDef):
            label = node.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            label = node.name
        next_parents = parents
        if label is not None and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            next_parents = [*parents, label]
            start = _abs_offset(offsets, node.lineno, node.col_offset)
            end = _abs_offset(offsets, node.end_lineno, node.end_col_offset)
            ranges.append(_ContextRange(" / ".join(next_parents), start, end, len(next_parents)))
        for child in ast.iter_child_nodes(node):
            walk(child, next_parents)

    walk(tree, [])
    return ranges


def _context_for_offset(ranges: list[_ContextRange], offset: int) -> str:
    matches = [r for r in ranges if r.start <= offset < r.end]
    if not matches:
        return "Module"
    matches.sort(key=lambda r: r.depth, reverse=True)
    return matches[0].label


def _selector_category(selector: str, fallback: str = "Settings") -> str:
    s = selector.lower()
    if "title" in s or "dialogcontainer" in s:
        return "Window"
    if "sidebar" in s or "tabbutton" in s:
        return "Navigation"
    if "contentarea" in s:
        return "Content"
    if "groupbox" in s:
        return "Panels"
    if any(term in s for term in ("pushbutton", "checkbox", "listwidget", "combobox", "spinbox", "slider", "label")):
        return "Controls"
    return fallback


def _property_label(prop: str) -> str:
    return _humanize(prop.replace("background-color", "background"))



def _css_comment_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"/\*.*?\*/", text, re.DOTALL)]


def _inside_spans(position: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _extract_property_before(raw: str, match_start: int) -> str:
    prefix = raw[max(0, match_start - 180):match_start]
    # The token may be a quoted Python string.  Find the final CSS property name.
    m = re.search(r"([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*[^:;{}]*$", prefix)
    return m.group(1) if m else "colour"


def _discover_structured_qss_string(
    source_path: str,
    source: str,
    assignment_name: str,
    namespace: str,
    fallback_category: str,
) -> list[ThemeToken]:
    """Discover friendly selector/property tokens inside a triple-string QSS assignment."""
    assignments = [a for a in _assignment_ranges(source) if a.name == assignment_name]
    if not assignments:
        return []
    # custom_styles/MENU_STYLE/SUBMENU_STYLE are each a single literal assignment.
    assignment = assignments[0]
    raw = source[assignment.start:assignment.end]
    tokens: list[ThemeToken] = []
    seen_ids: dict[str, int] = {}

    # It is safe to parse braces here because these known assignments are literal QSS.
    for block in re.finditer(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}", raw, re.DOTALL):
        selector = re.sub(r"/\*.*?\*/", "", block.group("selector"), flags=re.DOTALL).strip()
        selector = re.sub(r"^[rRuUbBfF]*[\"\']{3}", "", selector).strip()
        if not selector:
            continue
        body = block.group("body")
        body_comments = _css_comment_spans(body)
        body_abs = assignment.start + block.start("body")
        for declaration in re.finditer(r"(?P<prop>[A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(?P<value>[^;]+);", body):
            if _inside_spans(declaration.start(), body_comments):
                continue
            prop = declaration.group("prop").strip()
            value_text = declaration.group("value")
            value_abs = body_abs + declaration.start("value")
            for match, rgba, style in _iter_color_matches(value_text):
                base_id = f"{namespace}.{_slug(selector)}.{_slug(prop)}"
                seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
                token_id = base_id if seen_ids[base_id] == 1 else f"{base_id}_{seen_ids[base_id]}"
                label = f"{_humanize(selector)} · {_property_label(prop)}"
                tokens.append(
                    ThemeToken(
                        token_id=token_id,
                        label=label,
                        category=_selector_category(selector, fallback_category),
                        value=rgba,
                        source_path=source_path,
                        source_hint=f"{assignment_name}: {selector} / {prop}",
                        bindings=[Binding(source_path, value_abs + match.start(), value_abs + match.end(), style)],
                    )
                )
    return tokens


def _discover_style_assignment_literals(
    source_path: str,
    source: str,
    allow: Callable[[str], bool],
    namespace: str,
    category: str,
) -> list[ThemeToken]:
    """Discover colour literals in approved Python style-string assignments.

    This intentionally does not try to fully parse concatenated Python QSS.  Stable
    ids use the assignment name + occurrence, and the UI shows the nearby CSS
    property and source hint.
    """
    offsets = _line_offsets(source)
    assignments = [a for a in _assignment_ranges(source) if allow(a.name)]
    if not assignments:
        return []
    tokens: list[ThemeToken] = []
    occurrence: dict[str, int] = {}

    try:
        toks = tokenize.generate_tokens(io.StringIO(source).readline)
    except Exception:
        return []
    for tok in toks:
        if tok.type != tokenize.STRING:
            continue
        start = _abs_offset(offsets, tok.start[0], tok.start[1])
        end = _abs_offset(offsets, tok.end[0], tok.end[1])
        owner = next((a for a in assignments if a.start <= start and end <= a.end), None)
        if owner is None:
            continue
        raw = source[start:end]
        css_comments = _css_comment_spans(raw)
        for match, rgba, style in _iter_color_matches(raw):
            if _inside_spans(match.start(), css_comments):
                continue
            key = owner.name
            occurrence[key] = occurrence.get(key, 0) + 1
            idx = occurrence[key]
            prop = _extract_property_before(raw, match.start())
            token_id = f"{namespace}.{_slug(owner.name)}.{_slug(prop)}_{idx:02d}"
            tokens.append(
                ThemeToken(
                    token_id=token_id,
                    label=f"{_humanize(owner.name)} · {_property_label(prop)} {idx}",
                    category=category,
                    value=rgba,
                    source_path=source_path,
                    source_hint=f"{owner.name}, colour #{idx}",
                    bindings=[Binding(source_path, start + match.start(), start + match.end(), style)],
                )
            )
    return tokens


def _discover_generic_string_colors(
    source_path: str,
    source: str,
    namespace: str,
    category: str,
) -> list[ThemeToken]:
    offsets = _line_offsets(source)
    contexts = _context_ranges(source)
    counters: dict[str, int] = {}
    tokens: list[ThemeToken] = []
    try:
        toks = tokenize.generate_tokens(io.StringIO(source).readline)
    except Exception:
        return []
    for tok in toks:
        if tok.type != tokenize.STRING:
            continue
        start = _abs_offset(offsets, tok.start[0], tok.start[1])
        raw = source[start:_abs_offset(offsets, tok.end[0], tok.end[1])]
        context = _context_for_offset(contexts, start)
        css_comments = _css_comment_spans(raw)
        for match, rgba, style in _iter_color_matches(raw):
            if _inside_spans(match.start(), css_comments):
                continue
            prop = _extract_property_before(raw, match.start())
            # settings_dialog/about string scanning is intentionally stricter
            # than known *_STYLE assignments: only edit actual CSS declarations,
            # never prose/docstrings that happen to say "transparent" or contain
            # a colour literal.
            if prop == "colour":
                continue
            key = _slug(context)
            counters[key] = counters.get(key, 0) + 1
            idx = counters[key]
            tokens.append(
                ThemeToken(
                    token_id=f"{namespace}.{key}.string_{_slug(prop)}_{idx:02d}",
                    label=f"{context} · {_property_label(prop)} {idx}",
                    category=category,
                    value=rgba,
                    source_path=source_path,
                    source_hint=f"{context}, inline style colour #{idx}",
                    bindings=[Binding(source_path, start + match.start(), start + match.end(), style)],
                )
            )
    return tokens



def _python_string_comment_spans(source: str) -> list[tuple[int, int]]:
    offsets = _line_offsets(source)
    spans: list[tuple[int, int]] = []
    try:
        toks = tokenize.generate_tokens(io.StringIO(source).readline)
    except Exception:
        return spans
    for tok in toks:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        spans.append((
            _abs_offset(offsets, tok.start[0], tok.start[1]),
            _abs_offset(offsets, tok.end[0], tok.end[1]),
        ))
    return spans

def _discover_qcolors(
    source_path: str,
    source: str,
    namespace: str,
    category: str,
) -> list[ThemeToken]:
    contexts = _context_ranges(source)
    ignored = _python_string_comment_spans(source)
    counters: dict[str, int] = {}
    tokens: list[ThemeToken] = []
    for match in QCOLOR_RE.finditer(source):
        if _inside_spans(match.start(), ignored):
            continue
        context = _context_for_offset(contexts, match.start())
        key = _slug(context)
        counters[key] = counters.get(key, 0) + 1
        idx = counters[key]
        a = int(match.group("a")) if match.group("a") is not None else 255
        rgba = Rgba(int(match.group("r")), int(match.group("g")), int(match.group("b")), a).clamped()
        style = "qcolor4" if match.group("a") is not None else "qcolor3"
        tokens.append(
            ThemeToken(
                token_id=f"{namespace}.{key}.qcolor_{idx:02d}",
                label=f"{context} · QColor {idx}",
                category=category,
                value=rgba,
                source_path=source_path,
                source_hint=f"{context}, QColor #{idx}",
                bindings=[Binding(source_path, match.start(), match.end(), style)],
            )
        )
    return tokens


def _discover_dwm(source_path: str, source: str) -> list[ThemeToken]:
    """One semantic token for the Settings acrylic tint defaults."""
    func_match = re.search(
        r"def\s+enable_acrylic_blur\s*\((?P<sig>.*?)\)\s*->\s*bool\s*:",
        source,
        re.DOTALL,
    )
    if not func_match:
        return []
    sig = func_match.group("sig")
    sig_abs = func_match.start("sig")
    values: dict[str, int] = {}
    bindings: list[Binding] = []
    for channel, param in (("r", "tint_r"), ("g", "tint_g"), ("b", "tint_b"), ("a", "tint_alpha")):
        match = re.search(rf"\b{param}\s*:\s*int\s*=\s*(?P<value>\d{{1,3}})", sig)
        if not match:
            return []
        values[channel] = int(match.group("value"))
        bindings.append(
            Binding(
                source_path,
                sig_abs + match.start("value"),
                sig_abs + match.end("value"),
                "channel_int",
                channel,
            )
        )
    return [
        ThemeToken(
            token_id="settings.window.acrylic_tint",
            label="Windows Acrylic Tint",
            category="Window",
            value=Rgba(values["r"], values["g"], values["b"], values["a"]).clamped(),
            source_path=source_path,
            source_hint="enable_acrylic_blur() default tint",
            bindings=bindings,
        )
    ]


def _dedupe_tokens(tokens: Iterable[ThemeToken]) -> dict[str, ThemeToken]:
    result: dict[str, ThemeToken] = {}
    binding_spans: set[tuple[str, int, int]] = set()
    for token in tokens:
        spans = {(b.source_path, b.start, b.end) for b in token.bindings}
        if any(span in binding_spans for span in spans):
            continue
        candidate = token.token_id
        suffix = 2
        while candidate in result:
            candidate = f"{token.token_id}_{suffix}"
            suffix += 1
        token.token_id = candidate
        result[candidate] = token
        binding_spans.update(spans)
    return result


def _apply_friendly_overrides(tokens: dict[str, ThemeToken]) -> None:
    """Attach human-facing names/descriptions without changing stable token ids."""

    # High-value shell/settings tokens where source analysis gives us a useful
    # logical name.  The token id remains visible as the official identity.
    overrides: tuple[tuple[str, str, str, str], ...] = (
        (
            "settings.window.acrylic_tint",
            "Windows Acrylic Tint",
            "Window",
            "Native Windows acrylic/DWM tint behind the Settings Qt surfaces. Its alpha is tint strength, not a master opacity for everything drawn above it. Alpha 0 is a degenerate/unsupported acrylic edge case on some Windows builds.",
        ),
        (
            "settings.theme.customtitlebar.background_color",
            "Settings Title Bar Background",
            "Window",
            "Dark translucent surface behind the SRPSS SETTINGS title area. It is painted above the native acrylic backdrop.",
        ),
        (
            "settings.theme.dialogcontainer.background_color",
            "Outer Dialog Glass",
            "Window",
            "Very low-alpha Qt shell fill for the Settings dialog. Sidebar, content and title surfaces are painted above this layer.",
        ),
        (
            "settings.theme.sidebar.background_color",
            "Sidebar / Tab Block Background",
            "Navigation",
            "Background of the left Settings navigation block. Individual tab-button states are painted above it.",
        ),
        (
            "settings.theme.tabbutton.background_color",
            "Sidebar Tab Background",
            "Navigation",
            "Normal background of a Settings sidebar tab. Hover and selected states can override it.",
        ),
        (
            "settings.theme.tabbutton_hover.background_color",
            "Sidebar Tab Hover",
            "Navigation",
            "Background used while a Settings sidebar tab is hovered. This state overrides the normal tab background.",
        ),
        (
            "settings.theme.tabbutton_checked.background_color",
            "Sidebar Tab Selected",
            "Navigation",
            "Background used by the currently selected Settings sidebar tab. This state overrides the normal tab background.",
        ),
        (
            "settings.theme.contentarea.background_color",
            "Main Content Background",
            "Content",
            "Background of the right-hand Settings content host. It is intentionally transparent in the current theme, so most visible darkness comes from lower acrylic/shell layers and panels drawn above it.",
        ),
        (
            "settings.theme.qgroupbox.background_color",
            "Global Settings Group / Frame Background",
            "Panels",
            "Global QGroupBox background in the Settings theme. Many mature Settings subsections apply a later local group-box style, so this value can be partly or completely masked.",
        ),
        (
            "settings.controls.subsection_divider_style.background_color",
            "Subsection Panel Background",
            "Panels",
            "Local background used by style_group_box() for mature Settings subsection frames. It is commonly painted above the main content host and can override/mask the global QGroupBox background.",
        ),
    )
    for fragment, label, category, description in overrides:
        for token_id, token in tokens.items():
            if token_id.startswith(fragment):
                token.label = label
                token.category = category
                token.description = description

    # Context-menu names and intentional default link groups.
    for token in tokens.values():
        tid = token.token_id
        if tid.startswith("context.main.qmenu.background_color"):
            token.label = "Context Menu Background"
            token.default_link_group = "context.background"
            token.description = "Base background of the screensaver context menu. Item state backgrounds are painted above it."
        elif tid.startswith("context.submenu.qmenu.background_color"):
            token.label = "Context Submenu Background"
            token.default_link_group = "context.background"
            token.description = "Base background of context-menu submenus. Linked to the main menu background by default."
        elif tid.startswith("context.main.qmenu.border"):
            token.label = "Context Menu Border"
            token.default_link_group = "context.border"
            token.description = "Outer border of the screensaver context menu."
        elif tid.startswith("context.submenu.qmenu.border"):
            token.label = "Context Submenu Border"
            token.default_link_group = "context.border"
            token.description = "Outer border of screensaver context submenus."
        elif tid.startswith("context.main.qmenu_item.background_color"):
            token.label = "Context Menu Item Background"
            token.description = "Ordinary item background above the menu base. It is currently fully transparent, so its RGB channels are visually dormant until alpha is raised."
        elif tid.startswith("context.submenu.qmenu_item.background_color"):
            token.label = "Context Submenu Item Background"
            token.description = "Ordinary submenu item background above the submenu base. It is currently fully transparent, so its RGB channels are visually dormant until alpha is raised."
        elif tid.startswith("context.main.qmenu_item.color"):
            token.label = "Context Menu Text"
            token.default_link_group = "context.text"
            token.description = "Normal text colour for screensaver context-menu items."
        elif tid.startswith("context.submenu.qmenu_item.color"):
            token.label = "Context Submenu Text"
            token.default_link_group = "context.text"
            token.description = "Normal text colour for screensaver context-submenu items."
        elif "qmenu_item_selected.background_color" in tid:
            token.label = "Context Selected Background" if tid.startswith("context.main") else "Context Submenu Selected"
            token.default_link_group = "context.selected"
            token.description = "Selection-state background painted above the ordinary menu/item background."
        elif "qmenu_item_checked.background_color" in tid:
            token.label = "Context Checked Background"
            token.default_link_group = "context.selected"
            token.description = "Checked-state background for submenu items, painted above the submenu base."
        elif "qmenu_item_disabled.color" in tid:
            token.label = "Context Disabled Text"
            token.description = "Text colour/opacity for disabled context-menu items."
        elif "qmenu_separator.background_color" in tid:
            token.label = "Context Separator"
            token.description = "Colour and opacity of context-menu separator lines."

    # Remaining automatically discovered settings colours still get useful
    # Foundry-only descriptions.  We deliberately phrase uncertain mappings as
    # source-derived rather than pretending static analysis knows the full scene.
    for token in tokens.values():
        if token.description:
            continue
        if token.source_path == "ui/tabs/shared_styles.py":
            token.description = (
                f"Settings control/style colour discovered from {token.source_hint}. "
                "It may apply to a control state or local subsection style; inspect Known Layers for any mapped override relationships."
            )
        elif token.source_path == "ui/settings_dialog.py":
            token.description = f"Settings-dialog chrome/popup colour discovered from {token.source_hint}."
        elif token.source_path == "ui/settings_about_tab.py":
            token.description = f"About-page presentation colour discovered from {token.source_hint}."
        elif token.source_path == "widgets/context_menu.py":
            token.description = f"Screensaver context-menu presentation colour discovered from {token.source_hint}."
        else:
            token.description = f"Settings presentation colour discovered from {token.source_hint}."


# Curated high-confidence relationships.  Each rule reads:
#   lower/base fragment, upper/override fragment, relationship kind, explanation.
# Fragments are used because generated token suffixes can change as source styles
# evolve while the semantic selector/property prefix stays stable.
KNOWN_LAYER_RULES: tuple[tuple[str, str, str, str], ...] = (
    (
        "settings.window.acrylic_tint",
        "settings.theme.dialogcontainer.background_color",
        "composite",
        "The native acrylic/DWM backdrop is below the Qt Settings shell fill.",
    ),
    (
        "settings.window.acrylic_tint",
        "settings.theme.customtitlebar.background_color",
        "composite",
        "The Settings title bar paints above the native acrylic backdrop.",
    ),
    (
        "settings.window.acrylic_tint",
        "settings.theme.sidebar.background_color",
        "composite",
        "The sidebar/tab block paints above the native acrylic backdrop.",
    ),
    (
        "settings.window.acrylic_tint",
        "settings.theme.contentarea.background_color",
        "composite",
        "The main content host sits above the native acrylic backdrop; when transparent it exposes lower layers rather than controlling them.",
    ),
    (
        "settings.theme.dialogcontainer.background_color",
        "settings.theme.sidebar.background_color",
        "composite",
        "The sidebar is a child surface above the outer dialog glass.",
    ),
    (
        "settings.theme.dialogcontainer.background_color",
        "settings.theme.contentarea.background_color",
        "composite",
        "The content host is a child surface above the outer dialog glass.",
    ),
    (
        "settings.theme.contentarea.background_color",
        "settings.theme.qgroupbox.background_color",
        "composite",
        "Global Settings group boxes are panels painted above the content host.",
    ),
    (
        "settings.theme.contentarea.background_color",
        "settings.controls.subsection_divider_style.background_color",
        "composite",
        "Mature subsection panels are painted above the content host and can dominate its apparent opacity.",
    ),
    (
        "settings.theme.qgroupbox.background_color",
        "settings.controls.subsection_divider_style.background_color",
        "override",
        "style_group_box() applies a local QGroupBox stylesheet after the global Settings QGroupBox rule, so the local subsection fill can mask the global group-box fill.",
    ),
    (
        "settings.theme.sidebar.background_color",
        "settings.theme.tabbutton.background_color",
        "composite",
        "Individual navigation-tab backgrounds are painted above the sidebar block.",
    ),
    (
        "settings.theme.tabbutton.background_color",
        "settings.theme.tabbutton_hover.background_color",
        "state",
        "Hover state overrides the ordinary sidebar-tab background while active.",
    ),
    (
        "settings.theme.tabbutton.background_color",
        "settings.theme.tabbutton_checked.background_color",
        "state",
        "Checked/selected state overrides the ordinary sidebar-tab background while active.",
    ),
    (
        "context.main.qmenu.background_color",
        "context.main.qmenu_item.background_color",
        "composite",
        "Ordinary context-menu item backgrounds are painted above the menu base.",
    ),
    (
        "context.main.qmenu_item.background_color",
        "context.main.qmenu_item_selected.background_color",
        "state",
        "Selected state overrides the ordinary item background.",
    ),
    (
        "context.submenu.qmenu.background_color",
        "context.submenu.qmenu_item.background_color",
        "composite",
        "Ordinary submenu item backgrounds are painted above the submenu base.",
    ),
    (
        "context.submenu.qmenu_item.background_color",
        "context.submenu.qmenu_item_selected.background_color",
        "state",
        "Selected submenu state overrides the ordinary item background.",
    ),
    (
        "context.submenu.qmenu_item.background_color",
        "context.submenu.qmenu_item_checked.background_color",
        "state",
        "Checked submenu state overrides the ordinary item background.",
    ),
)


def _theme_foundry_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "SRPSS" / "ThemeFoundry"


def _preferences_path() -> Path:
    return _theme_foundry_data_dir() / "preferences.json"


def _load_favorites() -> set[str]:
    try:
        payload = json.loads(_preferences_path().read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            return set()
        raw = payload.get("favorites", [])
        if not isinstance(raw, list):
            return set()
        return {str(item) for item in raw if str(item).strip()}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return set()


def _save_favorites(favorites: set[str]) -> None:
    path = _preferences_path()
    payload = {
        "version": PREFERENCES_VERSION,
        "favorites": sorted(favorites),
    }
    try:
        _atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    except OSError:
        # Favorites are QoL state only; failure must never block theme editing.
        pass


def _alpha_over(top: Rgba, bottom: Rgba) -> Rgba:
    """Simple straight-alpha preview composite used only for Foundry estimates."""
    t = top.clamped()
    b = bottom.clamped()
    ta = t.a / 255.0
    ba = b.a / 255.0
    out_a = ta + ba * (1.0 - ta)
    if out_a <= 0.000001:
        return Rgba(0, 0, 0, 0)
    def channel(tc: int, bc: int) -> int:
        value = (tc * ta + bc * ba * (1.0 - ta)) / out_a
        return max(0, min(255, round(value)))
    return Rgba(channel(t.r, b.r), channel(t.g, b.g), channel(t.b, b.b), round(out_a * 255.0))


def discover_from_texts(text_by_path: Mapping[str, str]) -> DiscoveryResult:
    all_tokens: list[ThemeToken] = []
    warnings: list[str] = []
    sources: dict[str, SourceSnapshot] = {
        path: SourceSnapshot(text=text, sha256=_sha256_text(text)) for path, text in text_by_path.items()
    }

    for source_path, role, category in SOURCE_ROLES:
        source = text_by_path.get(source_path)
        if source is None:
            warnings.append(f"Missing source: {source_path}")
            continue

        if role == "settings_theme":
            structured = _discover_structured_qss_string(
                source_path, source, "custom_styles", "settings.theme", "Settings"
            )
            all_tokens.extend(structured)
            if not structured:
                warnings.append("Could not discover settings_theme.py custom_styles colours")

        elif role == "shared_styles":
            allow = STYLE_ASSIGNMENT_ALLOWLIST[source_path]
            all_tokens.extend(
                _discover_style_assignment_literals(
                    source_path, source, allow, "settings.controls", "Controls"
                )
            )
            all_tokens.extend(_discover_qcolors(source_path, source, "settings.controls", "Controls"))

        elif role == "settings_dialog":
            all_tokens.extend(_discover_generic_string_colors(source_path, source, "settings.chrome", "Settings Chrome"))
            all_tokens.extend(_discover_qcolors(source_path, source, "settings.chrome", "Settings Chrome"))

        elif role == "settings_about":
            all_tokens.extend(_discover_generic_string_colors(source_path, source, "settings.about", "About"))
            all_tokens.extend(_discover_qcolors(source_path, source, "settings.about", "About"))

        elif role == "dwm":
            tokens = _discover_dwm(source_path, source)
            all_tokens.extend(tokens)
            if not tokens:
                warnings.append("Could not discover Settings acrylic tint defaults")

        elif role == "context_menu":
            main_tokens = _discover_structured_qss_string(
                source_path, source, "MENU_STYLE", "context.main", "Context Menu"
            )
            sub_tokens = _discover_structured_qss_string(
                source_path, source, "SUBMENU_STYLE", "context.submenu", "Context Menu"
            )
            all_tokens.extend(main_tokens)
            all_tokens.extend(sub_tokens)
            if not main_tokens or not sub_tokens:
                warnings.append("Could not fully discover context-menu QSS colours")

    tokens = _dedupe_tokens(all_tokens)
    _apply_friendly_overrides(tokens)
    return DiscoveryResult(tokens=tokens, sources=sources, warnings=warnings)


def discover_repo(repo_root: Path) -> DiscoveryResult:
    text_by_path: dict[str, str] = {}
    warnings: list[str] = []
    for relpath, _role, _category in SOURCE_ROLES:
        path = repo_root / relpath
        if not path.is_file():
            warnings.append(f"Missing source: {relpath}")
            continue
        text_by_path[relpath] = path.read_text(encoding="utf-8")
    result = discover_from_texts(text_by_path)
    result.warnings[:0] = warnings
    diagnostic_path = repo_root / DIAGNOSTIC_QSS_PATH
    if diagnostic_path.is_file():
        try:
            result.diagnostic_sources[DIAGNOSTIC_QSS_PATH] = diagnostic_path.read_text(encoding="utf-8")
        except OSError as exc:
            result.warnings.append(f"Could not read diagnostic stylesheet {DIAGNOSTIC_QSS_PATH}: {exc}")
    return result


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return completed.stdout
    except Exception:
        return None


def git_head_sha(repo_root: Path) -> str | None:
    value = _git(repo_root, "rev-parse", "HEAD")
    return value.strip() if value else None


def discover_git_head(repo_root: Path) -> DiscoveryResult | None:
    if git_head_sha(repo_root) is None:
        return None
    text_by_path: dict[str, str] = {}
    for relpath, _role, _category in SOURCE_ROLES:
        text = _git(repo_root, "show", f"HEAD:{relpath}")
        if text is not None:
            text_by_path[relpath] = text
    if not text_by_path:
        return None
    result = discover_from_texts(text_by_path)
    diagnostic = _git(repo_root, "show", f"HEAD:{DIAGNOSTIC_QSS_PATH}")
    if diagnostic is not None:
        result.diagnostic_sources[DIAGNOSTIC_QSS_PATH] = diagnostic
    return result


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.theme-foundry-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def apply_token_values(
    repo_root: Path,
    discovery: DiscoveryResult,
    values: Mapping[str, Rgba],
) -> list[str]:
    """Apply all changed token values atomically per source after validation."""
    by_path: dict[str, list[tuple[Binding, Rgba]]] = {}
    for token_id, token in discovery.tokens.items():
        desired = values.get(token_id, token.value)
        if desired == token.value:
            continue
        for binding in token.bindings:
            by_path.setdefault(binding.source_path, []).append((binding, desired))

    if not by_path:
        return []

    # Validate all touched files before preparing any write.
    current_text: dict[str, str] = {}
    for relpath in by_path:
        path = repo_root / relpath
        text = path.read_text(encoding="utf-8")
        snapshot = discovery.sources.get(relpath)
        if snapshot is None or _sha256_text(text) != snapshot.sha256:
            raise RuntimeError(
                f"{relpath} changed after Theme Foundry loaded it. Reload Sources before applying; "
                "nothing was written."
            )
        current_text[relpath] = text

    prepared: dict[str, str] = {}
    for relpath, edits in by_path.items():
        text = current_text[relpath]
        # Every binding from this discovery must still match its source span by
        # hash validation.  Apply right-to-left so offsets remain valid.
        spans_seen: set[tuple[int, int]] = set()
        for binding, _value in edits:
            span = (binding.start, binding.end)
            if span in spans_seen:
                raise RuntimeError(f"Duplicate edit span discovered in {relpath}: {span}")
            spans_seen.add(span)
        for binding, value in sorted(edits, key=lambda item: item[0].start, reverse=True):
            text = text[:binding.start] + binding.render(value) + text[binding.end:]
        prepared[relpath] = text

    # Only after all files are prepared successfully do we replace them.
    for relpath, text in prepared.items():
        _atomic_write_text(repo_root / relpath, text)
    return sorted(prepared)


class ColorPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = Rgba(255, 255, 255, 255)
        self.setMinimumWidth(160)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_rgba(self, value: Rgba) -> None:
        self._color = value.clamped()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cell = 10
        c1 = QColor(55, 55, 55)
        c2 = QColor(90, 90, 90)
        for y in range(0, self.height(), cell):
            for x in range(0, self.width(), cell):
                painter.fillRect(QRect(x, y, cell, cell), c1 if ((x // cell) + (y // cell)) % 2 == 0 else c2)
        painter.fillRect(self.rect(), self._color.to_qcolor())
        pen = QPen(QColor(255, 255, 255, 140))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


class SwatchButton(QPushButton):
    colorRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = Rgba(255, 255, 255, 255)
        self.setText("Choose Colour…")
        self.clicked.connect(self.colorRequested.emit)
        self.setMinimumHeight(36)
        self._refresh()

    def set_rgba(self, value: Rgba) -> None:
        self._value = value.clamped()
        self._refresh()

    def _refresh(self) -> None:
        c = self._value
        fg = "#000000" if (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) > 150 else "#ffffff"
        # Button is only an editor preview, not part of the target theme.
        self.setStyleSheet(
            "QPushButton {"
            f"background-color: rgba({c.r},{c.g},{c.b},{c.a});"
            f"color: {fg}; border: 1px solid #aaaaaa; border-radius: 6px; padding: 6px 12px;"
            "}"
        )


class ThemeFoundryWindow(QMainWindow):
    """Developer-facing authoring UI for the narrow Settings/context-menu theme scope."""

    COL_FAV = 0
    COL_TOKEN = 1
    COL_STATE = 2
    COL_WORKING = 3
    COL_REPO = 4
    COL_LINK = 5

    def __init__(self, repo_root: Path) -> None:
        super().__init__()
        self.repo_root = repo_root.resolve()
        self.discovery = DiscoveryResult({}, {}, [])
        self.repo_discovery: DiscoveryResult | None = None
        self.values: dict[str, Rgba] = {}
        self.opened_values: dict[str, Rgba] = {}
        self.repo_values: dict[str, Rgba] = {}
        self.active_links: dict[str, str | None] = {}
        self.default_links: dict[str, str | None] = {}
        self.tree_items: dict[str, QTreeWidgetItem] = {}
        self.favorites: set[str] = _load_favorites()
        self._selected_id: str | None = None
        self._updating_editor = False
        self._theme_path: Path | None = None
        self._session_head = git_head_sha(self.repo_root)

        self.setWindowTitle(APP_TITLE)
        icon_path = self.repo_root / "images" / "foundries" / "SRPSSTheme.ico"
        if icon_path.is_file():
            foundry_icon = QIcon(str(icon_path))
            self.setWindowIcon(foundry_icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(foundry_icon)
        self.resize(1340, 860)
        self.setMinimumSize(1040, 680)
        self._build_ui()
        self._apply_internal_style()
        self.reload_sources(first_load=True)

    # ----- UI -----------------------------------------------------------
    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("themeFoundryRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        title = QLabel("THEME FOUNDRY")
        title.setObjectName("themeFoundryTitle")
        title_font = QFont(title.font())
        title_font.setPointSize(max(16, title_font.pointSize() + 6))
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        subtitle = QLabel(
            "Settings GUI + screensaver context-menu palette laboratory · canonical source editor · full .srtheme snapshots"
        )
        subtitle.setObjectName("themeFoundrySubtitle")
        outer.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.reload_btn = QPushButton("Reload Sources")
        self.load_btn = QPushButton("Load Theme…")
        self.save_btn = QPushButton("Save Theme…")
        self.apply_btn = QPushButton("Apply to Sources")
        self.apply_btn.setObjectName("themeFoundryPrimary")
        self.launch_btn = QPushButton("Launch Settings (--s)")
        toolbar.addWidget(self.reload_btn)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.apply_btn)
        toolbar.addWidget(self.launch_btn)
        outer.addLayout(toolbar)

        scope = QLabel(
            "Scope is deliberately hard-bounded: Settings GUI + screensaver context menu only. "
            "Runtime widgets, visualizers, transition rendering, overlays and cursor halo are not discovered or edited."
        )
        scope.setWordWrap(True)
        scope.setObjectName("scopeBanner")
        outer.addWidget(scope)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)

        left = QWidget()
        left.setObjectName("themeFoundryPane")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("sidebar, content, acrylic, context, shadow…")
        search_row.addWidget(self.search, 1)
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories")
        search_row.addWidget(self.category_filter)
        self.favorites_only = QCheckBox("★ Favorites")
        self.favorites_only.setToolTip("Show only starred Theme Foundry tokens")
        search_row.addWidget(self.favorites_only)
        left_layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setObjectName("themeFoundryTree")
        self.tree.setHeaderLabels(["★", "Theme token", "State", "Working", "Repo default", "Link"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        header.setSectionResizeMode(self.COL_FAV, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TOKEN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_STATE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_WORKING, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_REPO, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_LINK, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.tree, 1)
        splitter.addWidget(left)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor = QWidget()
        editor.setObjectName("themeFoundryEditor")
        right_scroll.setWidget(editor)
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(14, 4, 8, 6)
        editor_layout.setSpacing(10)

        title_row = QHBoxLayout()
        self.token_title = QLabel("Select a theme token")
        self.token_title.setObjectName("tokenTitle")
        font = QFont(self.token_title.font())
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.token_title.setFont(font)
        title_row.addWidget(self.token_title, 1)
        self.favorite_btn = QPushButton("☆ Favorite")
        self.favorite_btn.setObjectName("favoriteButton")
        self.favorite_btn.setToolTip("Star this token for quick filtering. Favorites are Foundry preferences, not theme data.")
        title_row.addWidget(self.favorite_btn)
        editor_layout.addLayout(title_row)

        self.token_source = QLabel("")
        self.token_source.setWordWrap(True)
        self.token_source.setObjectName("muted")
        editor_layout.addWidget(self.token_source)

        self.token_description = QLabel("")
        self.token_description.setWordWrap(True)
        self.token_description.setObjectName("descriptionBox")
        editor_layout.addWidget(self.token_description)

        self.state_banner = QLabel("")
        self.state_banner.setWordWrap(True)
        self.state_banner.setObjectName("stateBanner")
        editor_layout.addWidget(self.state_banner)

        preview_grid = QGridLayout()
        preview_grid.setHorizontalSpacing(12)
        preview_grid.setVerticalSpacing(6)

        isolated_label = QLabel("Isolated colour / alpha")
        isolated_label.setObjectName("previewLabel")
        preview_grid.addWidget(isolated_label, 0, 0)

        composite_label = QLabel("Estimated with nearest known layer")
        composite_label.setObjectName("previewLabel")
        composite_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        preview_grid.addWidget(composite_label, 0, 1)

        self.preview = ColorPreview()
        preview_grid.addWidget(self.preview, 1, 0)
        self.composite_preview = ColorPreview()
        preview_grid.addWidget(self.composite_preview, 1, 1)

        self.composite_note = QLabel("No mapped compositing neighbour")
        self.composite_note.setWordWrap(True)
        self.composite_note.setObjectName("muted")
        self.composite_note.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        preview_grid.addWidget(self.composite_note, 2, 1)

        preview_grid.setColumnStretch(0, 1)
        preview_grid.setColumnStretch(1, 1)
        editor_layout.addLayout(preview_grid)

        self.swatch = SwatchButton()
        editor_layout.addWidget(self.swatch)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.r_spin = self._channel_spin()
        self.g_spin = self._channel_spin()
        self.b_spin = self._channel_spin()
        form.addRow("Red", self.r_spin)
        form.addRow("Green", self.g_spin)
        form.addRow("Blue", self.b_spin)

        alpha_wrap = QWidget()
        alpha_row = QHBoxLayout(alpha_wrap)
        alpha_row.setContentsMargins(0, 0, 0, 0)
        self.a_slider = QSlider(Qt.Orientation.Horizontal)
        self.a_slider.setRange(0, 255)
        self.a_spin = self._channel_spin()
        self.alpha_pct = QLabel("100.0%")
        self.alpha_pct.setMinimumWidth(58)
        alpha_row.addWidget(self.a_slider, 1)
        alpha_row.addWidget(self.a_spin)
        alpha_row.addWidget(self.alpha_pct)
        form.addRow("Opacity", alpha_wrap)
        editor_layout.addLayout(form)

        values_box = QFrame()
        values_box.setObjectName("valuesBox")
        values_layout = QGridLayout(values_box)
        values_layout.addWidget(QLabel("Opened"), 0, 0)
        values_layout.addWidget(QLabel("Repository default"), 1, 0)
        values_layout.addWidget(QLabel("Working"), 2, 0)
        self.opened_label = QLabel("—")
        self.repo_label = QLabel("—")
        self.working_label = QLabel("—")
        values_layout.addWidget(self.opened_label, 0, 1)
        values_layout.addWidget(self.repo_label, 1, 1)
        values_layout.addWidget(self.working_label, 2, 1)
        editor_layout.addWidget(values_box)

        link_row = QHBoxLayout()
        self.link_btn = QPushButton("🔗 Linked")
        self.link_btn.setToolTip("Toggle intentional palette linkage. This is separate from visual layering.")
        self.link_info = QLabel("")
        self.link_info.setWordWrap(True)
        link_row.addWidget(self.link_btn)
        link_row.addWidget(self.link_info, 1)
        editor_layout.addLayout(link_row)

        layers_heading = QLabel("KNOWN VISUAL / STYLE LAYERS")
        layers_heading.setObjectName("sectionHeading")
        editor_layout.addWidget(layers_heading)
        layers_help = QLabel(
            "These are high-confidence relationships inferred from current SRPSS source. "
            "They explain why changing one alpha can have little visible effect. Double-click an editable related token to jump to it."
        )
        layers_help.setWordWrap(True)
        layers_help.setObjectName("muted")
        editor_layout.addWidget(layers_help)
        self.layers_tree = QTreeWidget()
        self.layers_tree.setObjectName("layersTree")
        self.layers_tree.setHeaderLabels(["Relationship", "Layer / override", "Why it matters"])
        self.layers_tree.setRootIsDecorated(False)
        self.layers_tree.setAlternatingRowColors(True)
        self.layers_tree.setMinimumHeight(150)
        layers_header = self.layers_tree.header()
        layers_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        layers_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layers_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        editor_layout.addWidget(self.layers_tree)

        reset_row = QHBoxLayout()
        self.reset_opened_btn = QPushButton("Reset to Opened")
        self.reset_repo_btn = QPushButton("Reset to Repo Default")
        reset_row.addWidget(self.reset_opened_btn)
        reset_row.addWidget(self.reset_repo_btn)
        editor_layout.addLayout(reset_row)

        self.reset_all_opened_btn = QPushButton("Reset ALL Editable Tokens to Opened Values")
        self.reset_all_repo_btn = QPushButton("Reset ALL Editable Tokens to Repo Defaults")
        editor_layout.addWidget(self.reset_all_opened_btn)
        editor_layout.addWidget(self.reset_all_repo_btn)
        editor_layout.addStretch(1)
        splitter.addWidget(right_scroll)
        splitter.setSizes([800, 500])

        status = QStatusBar(self)
        self.setStatusBar(status)
        self.status_label = QLabel("")
        status.addWidget(self.status_label, 1)

        self.reload_btn.clicked.connect(self.reload_sources)
        self.load_btn.clicked.connect(self.load_theme)
        self.save_btn.clicked.connect(self.save_theme)
        self.apply_btn.clicked.connect(self.apply_to_sources)
        self.launch_btn.clicked.connect(self.launch_settings)
        self.search.textChanged.connect(self._filter_tree)
        self.category_filter.currentTextChanged.connect(self._filter_tree)
        self.favorites_only.toggled.connect(self._filter_tree)
        self.tree.currentItemChanged.connect(self._tree_selection_changed)
        self.tree.itemClicked.connect(self._tree_item_clicked)
        self.layers_tree.itemDoubleClicked.connect(self._layer_item_activated)
        self.favorite_btn.clicked.connect(self._toggle_selected_favorite)
        self.swatch.colorRequested.connect(self._choose_color)
        self.r_spin.valueChanged.connect(self._editor_value_changed)
        self.g_spin.valueChanged.connect(self._editor_value_changed)
        self.b_spin.valueChanged.connect(self._editor_value_changed)
        self.a_spin.valueChanged.connect(self._alpha_spin_changed)
        self.a_slider.valueChanged.connect(self._alpha_slider_changed)
        self.link_btn.clicked.connect(self._toggle_link)
        self.reset_opened_btn.clicked.connect(self._reset_selected_opened)
        self.reset_repo_btn.clicked.connect(self._reset_selected_repo)
        self.reset_all_opened_btn.clicked.connect(self._reset_all_opened)
        self.reset_all_repo_btn.clicked.connect(self._reset_all_repo)

    def _channel_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 255)
        spin.setMinimumWidth(88)
        return spin

    def _apply_internal_style(self) -> None:
        # Self-contained developer-tool skin: visually related to Build/Defaults
        # Foundry, but never sourced from the Settings theme being edited.
        self.setStyleSheet(
            """
            QMainWindow { background: #0d181e; color: #f4f0e6; }
            QWidget { color: #f4f0e6; font-family: 'Jost', 'Segoe UI', sans-serif; }
            QWidget#themeFoundryRoot {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13,24,30,255), stop:0.55 rgba(24,30,31,255), stop:1 rgba(41,34,24,255));
            }
            QWidget#themeFoundryPane, QWidget#themeFoundryEditor {
                background: rgba(10,15,17,150);
                border: 1px solid rgba(225,193,127,90);
                border-radius: 10px;
            }
            QLabel#themeFoundryTitle { color: #f4c66d; letter-spacing: 2px; }
            QLabel#themeFoundrySubtitle { color: #c8d4d1; font-size: 12px; padding-bottom: 3px; }
            QLabel#scopeBanner, QLabel#descriptionBox, QLabel#stateBanner {
                background: rgba(16,25,27,210); border: 1px solid rgba(225,193,127,110);
                border-radius: 8px; padding: 8px; color: #dce5df;
            }
            QLabel#stateBanner { color: #f4c66d; }
            QLabel#muted { color: #9fb2ad; }
            QLabel#previewLabel, QLabel#sectionHeading { color: #f4c66d; font-weight: 700; letter-spacing: 0.6px; }
            QLabel#tokenTitle { color: #f4f0e6; }
            QLineEdit, QComboBox, QSpinBox {
                background: #1f2626; color: #f4f0e6; border: 1px solid #8f7950;
                border-radius: 7px; padding: 5px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: transparent;
                border: none;
                width: 18px;
            }
            QTreeWidget#themeFoundryTree, QTreeWidget#layersTree {
                background-color: rgba(10,15,17,218);
                alternate-background-color: rgba(31,38,38,205);
                border: 1px solid rgba(225,193,127,150);
                border-radius: 10px; color: #edf1ed; outline: none;
            }
            QTreeWidget#themeFoundryTree::item, QTreeWidget#layersTree::item { min-height: 28px; padding: 2px 5px; }
            QTreeWidget#themeFoundryTree::item:selected, QTreeWidget#layersTree::item:selected { background: rgba(60,108,103,210); }
            QHeaderView::section {
                background: rgba(31,47,48,245); color: #f4c66d; border: none;
                border-right: 1px solid rgba(255,255,255,35); padding: 7px; font-weight: 700;
            }
            QPushButton {
                background: #263b3a; color: #f4f0e6; border: 1px solid #8f7950;
                border-radius: 7px; padding: 7px 12px; font-weight: 600;
            }
            QPushButton:hover { background: #33504d; border-color: #f4c66d; }
            QPushButton:disabled { color: #6f7e7b; border-color: #4f554e; background: #1b2424; }
            QPushButton#themeFoundryPrimary { background: #d59b42; color: #101719; border-color: #f4c66d; }
            QPushButton#themeFoundryPrimary:hover { background: #efb65a; }
            QPushButton#favoriteButton { min-width: 105px; }
            QFrame#valuesBox { border: 1px solid rgba(225,193,127,110); border-radius: 8px; background: rgba(16,25,27,205); }
            QCheckBox { spacing: 6px; }
            QSlider::groove:horizontal { height: 5px; background: #11191b; border: 1px solid #8f7950; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #f4c66d; border: 1px solid #fff0c5; }
            QStatusBar { background: #0a0f11; color: #c8d4d1; border-top: 1px solid rgba(225,193,127,90); }
            """
        )

    # ----- data lifecycle ------------------------------------------------
    def reload_sources(self, checked: bool = False, *, first_load: bool = False) -> None:
        del checked
        selected = self._selected_id
        previous_opened = dict(self.opened_values)
        try:
            discovery = discover_repo(self.repo_root)
            repo_discovery = discover_git_head(self.repo_root)
        except Exception as exc:
            self._error("Reload failed", str(exc))
            return
        if not discovery.tokens:
            self._error(
                "No editable theme tokens found",
                f"Theme Foundry could not discover supported tokens under:\n{self.repo_root}",
            )
            return

        self.discovery = discovery
        self.repo_discovery = repo_discovery
        self.values = {tid: token.value for tid, token in discovery.tokens.items()}
        if first_load or not previous_opened:
            self.opened_values = dict(self.values)
        else:
            self.opened_values = {tid: previous_opened.get(tid, value) for tid, value in self.values.items()}
        self.repo_values = (
            {tid: token.value for tid, token in repo_discovery.tokens.items() if tid in discovery.tokens}
            if repo_discovery is not None
            else {}
        )
        self.default_links = {tid: token.default_link_group for tid, token in discovery.tokens.items()}
        if first_load or not self.active_links:
            self.active_links = dict(self.default_links)
            self._drop_invalid_default_links()
        else:
            self.active_links = {tid: self.active_links.get(tid, self.default_links.get(tid)) for tid in discovery.tokens}
        self.favorites.intersection_update(set(discovery.tokens))
        self._rebuild_tree(selected)
        diagnostic = " · dark.qss diagnostics loaded" if DIAGNOSTIC_QSS_PATH in discovery.diagnostic_sources else ""
        warning_text = f" · {len(discovery.warnings)} source warning(s)" if discovery.warnings else ""
        self._set_status(f"Loaded {len(self.values)} editable theme tokens{diagnostic}{warning_text}")
        if discovery.warnings and first_load:
            self._warning("Theme discovery warnings", "\n".join(discovery.warnings[:12]))

    def _drop_invalid_default_links(self) -> None:
        groups: dict[str, list[str]] = {}
        for tid, group in self.active_links.items():
            if group:
                groups.setdefault(group, []).append(tid)
        for group, ids in groups.items():
            if len(ids) < 2:
                continue
            values = {self.values.get(tid) for tid in ids}
            if len(values) > 1:
                for tid in ids:
                    self.active_links[tid] = None

    # ----- metadata/layers ----------------------------------------------
    def _find_token_ids(self, fragment: str) -> list[str]:
        return [tid for tid in self.discovery.tokens if tid.startswith(fragment)]

    def _token_state(self, tid: str) -> tuple[str, str]:
        value = self.values.get(tid, self.discovery.tokens[tid].value)
        token = self.discovery.tokens[tid]
        if tid == "settings.window.acrylic_tint" and value.a == 0:
            return (
                "⚠ DWM α=0",
                "Acrylic alpha 0 is a degenerate/unsupported edge case on some Windows versions. It can disable or change the native effect instead of producing a perfectly clear acrylic backdrop.",
            )
        if value.a == 0:
            return (
                "○ α=0",
                "Currently fully transparent: its RGB channels have no visible effect until opacity is raised above zero.",
            )
        if value.a < 255:
            return (f"α {value.alpha_percent:.0f}%", "Currently translucent; lower visual layers can contribute to the final result.")
        if "background" in token.token_id or "border" in token.token_id:
            return ("Opaque", "Currently fully opaque at this token's own layer.")
        return ("Active", "Current value is visually active at this token's own layer.")

    def _dark_qss_matches(self, token: ThemeToken) -> list[str]:
        source = self.discovery.diagnostic_sources.get(DIAGNOSTIC_QSS_PATH)
        if not source or token.source_path != "ui/settings_theme.py":
            return []
        match = re.match(r"custom_styles:\s*(?P<selector>.*?)\s*/\s*(?P<prop>[A-Za-z0-9_-]+)\s*$", token.source_hint)
        if not match:
            return []
        selector = match.group("selector").strip()
        prop = match.group("prop").strip()
        results: list[str] = []
        # A deliberately modest diagnostic parser: exact selector blocks only.
        for block in re.finditer(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}", source, re.DOTALL):
            selectors = [s.strip() for s in re.sub(r"/\*.*?\*/", "", block.group("selector"), flags=re.DOTALL).split(",")]
            if selector not in selectors:
                continue
            declaration = re.search(rf"\b{re.escape(prop)}\s*:\s*(?P<value>[^;]+);", block.group("body"), re.IGNORECASE)
            if declaration:
                results.append(declaration.group("value").strip())
        return results

    def _layer_entries(self, tid: str) -> list[tuple[str, str, str, str | None]]:
        entries: list[tuple[str, str, str, str | None]] = []
        for lower_fragment, upper_fragment, kind, why in KNOWN_LAYER_RULES:
            lowers = self._find_token_ids(lower_fragment)
            uppers = self._find_token_ids(upper_fragment)
            if tid in lowers:
                for other in uppers:
                    relation = "STATE ABOVE" if kind == "state" else ("OVERRIDES THIS" if kind == "override" else "ABOVE THIS")
                    entries.append((relation, self.discovery.tokens[other].label, why, other))
            elif tid in uppers:
                for other in lowers:
                    relation = "STATE BASE" if kind == "state" else ("OVERRIDES" if kind == "override" else "BELOW THIS")
                    entries.append((relation, self.discovery.tokens[other].label, why, other))

        token = self.discovery.tokens[tid]
        for value in self._dark_qss_matches(token):
            entries.append((
                "EARLIER QSS",
                "themes/dark.qss",
                f"The base dark stylesheet contains the same selector/property with value {value}. settings_theme.py custom_styles is appended later, so the editable token normally wins; this earlier rule is shown read-only for override diagnosis.",
                None,
            ))
        return entries

    def _estimated_composite(self, tid: str) -> tuple[Rgba, str]:
        selected = self.values[tid]
        # Prefer actual compositing relationships over state/override rules.
        for lower_fragment, upper_fragment, kind, why in KNOWN_LAYER_RULES:
            if kind != "composite":
                continue
            lowers = self._find_token_ids(lower_fragment)
            uppers = self._find_token_ids(upper_fragment)
            if tid in lowers and uppers:
                upper = uppers[0]
                return _alpha_over(self.values[upper], selected), f"Estimate: {self.discovery.tokens[upper].label} over this token"
            if tid in uppers and lowers:
                lower = lowers[0]
                return _alpha_over(selected, self.values[lower]), f"Estimate: this token over {self.discovery.tokens[lower].label}"
        # Checkerboard preview already handles intrinsic alpha; use a neutral dark
        # backing for tokens with no mapped compositing neighbour.
        return _alpha_over(selected, Rgba(24, 30, 31, 255)), "No mapped neighbour; shown over Theme Foundry's neutral dark reference"

    def _tree_tooltip(self, tid: str) -> str:
        token = self.discovery.tokens[tid]
        state, state_detail = self._token_state(tid)
        layer_count = len(self._layer_entries(tid))
        return (
            f"{token.label}\n\nOfficial token: {token.official_name}\n"
            f"Source: {token.source_path}\n{token.source_hint}\n\n"
            f"{token.description}\n\nState: {state} — {state_detail}\n"
            f"Known layer/override relationships: {layer_count}"
        )

    # ----- tree -----------------------------------------------------------
    def _rebuild_tree(self, select_id: str | None = None) -> None:
        self.tree.clear()
        self.tree_items.clear()
        categories = sorted({token.category for token in self.discovery.tokens.values()})
        current_filter = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All categories")
        self.category_filter.addItems(categories)
        if current_filter in {"All categories", *categories}:
            self.category_filter.setCurrentText(current_filter)
        self.category_filter.blockSignals(False)

        parents: dict[str, QTreeWidgetItem] = {}
        for category in categories:
            parent = QTreeWidgetItem(["", category])
            font = parent.font(self.COL_TOKEN)
            font.setBold(True)
            parent.setFont(self.COL_TOKEN, font)
            self.tree.addTopLevelItem(parent)
            parents[category] = parent

        for tid, token in sorted(self.discovery.tokens.items(), key=lambda item: (item[1].category, item[1].label.lower(), item[0])):
            value = self.values[tid]
            repo = self.repo_values.get(tid)
            state, _detail = self._token_state(tid)
            item = QTreeWidgetItem(
                [
                    "★" if tid in self.favorites else "☆",
                    token.label,
                    state,
                    self._short_value(value),
                    self._short_value(repo) if repo else "—",
                    "🔗" if self.active_links.get(tid) else ("⛓" if self.default_links.get(tid) else ""),
                ]
            )
            item.setData(self.COL_FAV, Qt.ItemDataRole.UserRole, tid)
            item.setToolTip(self.COL_TOKEN, self._tree_tooltip(tid))
            item.setToolTip(self.COL_STATE, self._token_state(tid)[1])
            item.setTextAlignment(self.COL_FAV, Qt.AlignmentFlag.AlignCenter)
            parents[token.category].addChild(item)
            self.tree_items[tid] = item
        self.tree.expandAll()
        self._filter_tree()

        target = select_id if select_id in self.tree_items else next(iter(self.tree_items), None)
        if target:
            self.tree.setCurrentItem(self.tree_items[target])

    def _filter_tree(self, *args) -> None:
        del args
        text = self.search.text().strip().lower()
        category = self.category_filter.currentText()
        favorites_only = self.favorites_only.isChecked()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            visible_children = 0
            for j in range(parent.childCount()):
                item = parent.child(j)
                tid = item.data(self.COL_FAV, Qt.ItemDataRole.UserRole)
                token = self.discovery.tokens.get(tid)
                if token is None:
                    item.setHidden(True)
                    continue
                category_ok = category == "All categories" or token.category == category
                favorite_ok = not favorites_only or tid in self.favorites
                state, state_detail = self._token_state(tid)
                haystack = " ".join((
                    token.label, token.token_id, token.source_path, token.source_hint,
                    token.description, token.category, state, state_detail,
                )).lower()
                text_ok = not text or text in haystack
                visible = category_ok and favorite_ok and text_ok
                item.setHidden(not visible)
                if visible:
                    visible_children += 1
            parent.setHidden(visible_children == 0)

    def _tree_selection_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        tid = current.data(self.COL_FAV, Qt.ItemDataRole.UserRole)
        if not tid or tid not in self.discovery.tokens:
            return
        self._selected_id = str(tid)
        self._refresh_editor()

    def _tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if column != self.COL_FAV:
            return
        tid = item.data(self.COL_FAV, Qt.ItemDataRole.UserRole)
        if tid in self.discovery.tokens:
            self._toggle_favorite(str(tid))

    def _toggle_favorite(self, tid: str) -> None:
        if tid in self.favorites:
            self.favorites.remove(tid)
        else:
            self.favorites.add(tid)
        _save_favorites(self.favorites)
        self._refresh_tree_item(tid)
        self._filter_tree()
        if tid == self._selected_id:
            self._refresh_editor()

    def _toggle_selected_favorite(self) -> None:
        if self._selected_id:
            self._toggle_favorite(self._selected_id)

    def _layer_item_activated(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        tid = item.data(0, Qt.ItemDataRole.UserRole)
        if tid and tid in self.tree_items:
            self.tree.setCurrentItem(self.tree_items[tid])
            self.tree.scrollToItem(self.tree_items[tid])

    # ----- editor ---------------------------------------------------------
    def _refresh_editor(self) -> None:
        tid = self._selected_id
        if tid is None or tid not in self.discovery.tokens:
            return
        token = self.discovery.tokens[tid]
        value = self.values[tid]
        state, state_detail = self._token_state(tid)
        self._updating_editor = True
        try:
            self.token_title.setText(token.label)
            self.favorite_btn.setText("★ Favorite" if tid in self.favorites else "☆ Favorite")
            self.token_source.setText(
                f"Official token: {token.official_name}\nSource: {token.source_path} · {token.source_hint}"
            )
            self.token_description.setText(token.description)
            self.state_banner.setText(f"{state}  ·  {state_detail}")
            self.preview.set_rgba(value)
            composite, composite_note = self._estimated_composite(tid)
            self.composite_preview.set_rgba(composite)
            self.composite_note.setText(composite_note)
            self.swatch.set_rgba(value)
            self.r_spin.setValue(value.r)
            self.g_spin.setValue(value.g)
            self.b_spin.setValue(value.b)
            self.a_spin.setValue(value.a)
            self.a_slider.setValue(value.a)
            self.alpha_pct.setText(f"{value.alpha_percent:.1f}%")
            self.opened_label.setText(self._full_value(self.opened_values.get(tid)))
            self.repo_label.setText(self._full_value(self.repo_values.get(tid)))
            self.working_label.setText(self._full_value(value))
            default_group = self.default_links.get(tid)
            active_group = self.active_links.get(tid)
            self.link_btn.setEnabled(default_group is not None)
            self.link_btn.setText("🔗 Linked" if active_group else ("⛓ Relink" if default_group else "No link group"))
            if default_group:
                member_labels = [
                    self.discovery.tokens[mid].label
                    for mid, group in self.active_links.items()
                    if group == default_group and mid != tid and mid in self.discovery.tokens
                ]
                if active_group:
                    self.link_info.setText(
                        f"Linked palette group: {default_group}. "
                        + ("Also: " + ", ".join(member_labels) if member_labels else "")
                    )
                else:
                    self.link_info.setText(f"Unlinked from default palette group: {default_group}")
            else:
                self.link_info.setText("No intentional colour-link group. Visual layering is listed separately below.")
            self.reset_repo_btn.setEnabled(tid in self.repo_values)

            self.layers_tree.clear()
            entries = self._layer_entries(tid)
            if not entries:
                no_item = QTreeWidgetItem(["—", "No mapped relationship", "Static source analysis has no high-confidence layer/override mapping for this token yet."])
                self.layers_tree.addTopLevelItem(no_item)
            else:
                for relation, label, why, related_tid in entries:
                    item = QTreeWidgetItem([relation, label, why])
                    if related_tid:
                        item.setData(0, Qt.ItemDataRole.UserRole, related_tid)
                        item.setToolTip(1, "Double-click to jump to this editable token")
                    self.layers_tree.addTopLevelItem(item)
        finally:
            self._updating_editor = False

    def _choose_color(self) -> None:
        tid = self._selected_id
        if tid is None:
            return
        initial = self.values[tid].to_qcolor()
        dialog = QColorDialog(initial, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dialog.setWindowTitle(f"Choose {self.discovery.tokens[tid].label}")
        if dialog.exec() != QColorDialog.DialogCode.Accepted:
            return
        c = dialog.selectedColor()
        self._set_token_value(tid, Rgba(c.red(), c.green(), c.blue(), c.alpha()))

    def _editor_value_changed(self, value: int) -> None:
        del value
        if self._updating_editor or self._selected_id is None:
            return
        current = self.values[self._selected_id]
        self._set_token_value(
            self._selected_id,
            Rgba(self.r_spin.value(), self.g_spin.value(), self.b_spin.value(), current.a),
        )

    def _alpha_spin_changed(self, value: int) -> None:
        if self._updating_editor or self._selected_id is None:
            return
        self._updating_editor = True
        try:
            self.a_slider.setValue(value)
        finally:
            self._updating_editor = False
        current = self.values[self._selected_id]
        self._set_token_value(self._selected_id, Rgba(current.r, current.g, current.b, value))

    def _alpha_slider_changed(self, value: int) -> None:
        if self._updating_editor or self._selected_id is None:
            return
        self._updating_editor = True
        try:
            self.a_spin.setValue(value)
        finally:
            self._updating_editor = False
        current = self.values[self._selected_id]
        self._set_token_value(self._selected_id, Rgba(current.r, current.g, current.b, value))

    def _set_token_value(self, tid: str, value: Rgba, *, propagate: bool = True) -> None:
        value = value.clamped()
        targets = {tid}
        group = self.active_links.get(tid) if propagate else None
        if group:
            targets.update(mid for mid, linked_group in self.active_links.items() if linked_group == group)
        for target in targets:
            if target in self.values:
                self.values[target] = value
                self._refresh_tree_item(target)
        self._refresh_editor()
        self._update_dirty_status()

    def _toggle_link(self) -> None:
        tid = self._selected_id
        if tid is None:
            return
        default_group = self.default_links.get(tid)
        if not default_group:
            return
        if self.active_links.get(tid):
            self.active_links[tid] = None
        else:
            anchor = next(
                (mid for mid, group in self.active_links.items() if group == default_group and mid != tid),
                None,
            )
            self.active_links[tid] = default_group
            if anchor and anchor in self.values:
                self.values[tid] = self.values[anchor]
        self._rebuild_tree(tid)
        self._refresh_editor()
        self._update_dirty_status()

    def _reset_selected_opened(self) -> None:
        tid = self._selected_id
        if tid and tid in self.opened_values:
            self._set_token_value(tid, self.opened_values[tid])

    def _reset_selected_repo(self) -> None:
        tid = self._selected_id
        if tid and tid in self.repo_values:
            self._set_token_value(tid, self.repo_values[tid])

    def _reset_all_opened(self) -> None:
        if QMessageBox.question(
            self,
            "Reset all to opened values",
            "Reset every editable Theme Foundry token to the value it had when this session opened?\n\n"
            "This changes the working editor state only; use Apply to Sources to write it.",
        ) != QMessageBox.StandardButton.Yes:
            return
        for tid, value in self.opened_values.items():
            if tid in self.values:
                self.values[tid] = value
        self._rebuild_tree(self._selected_id)
        self._refresh_editor()
        self._update_dirty_status()

    def _reset_all_repo(self) -> None:
        if not self.repo_values:
            self._warning("Repository defaults unavailable", "Git HEAD defaults could not be read for this repository.")
            return
        if QMessageBox.question(
            self,
            "Reset all to repository defaults",
            "Reset every editable Theme Foundry token to its current Git HEAD value?\n\n"
            "This changes the working editor state only; use Apply to Sources to write it.",
        ) != QMessageBox.StandardButton.Yes:
            return
        for tid, value in self.repo_values.items():
            if tid in self.values:
                self.values[tid] = value
        self._rebuild_tree(self._selected_id)
        self._refresh_editor()
        self._update_dirty_status()

    # ----- theme files ----------------------------------------------------
    def _theme_payload(self) -> dict[str, object]:
        groups: dict[str, list[str]] = {}
        for tid, group in self.active_links.items():
            if group and tid in self.values:
                groups.setdefault(group, []).append(tid)
        links = [sorted(ids) for _group, ids in sorted(groups.items()) if len(ids) >= 2]
        tokens = {
            tid: {
                "rgba": self.values[tid].to_json(),
                "label": token.label,
                "category": token.category,
            }
            for tid, token in sorted(self.discovery.tokens.items())
        }
        return {
            "format": THEME_FORMAT,
            "version": THEME_VERSION,
            "name": self._theme_path.stem if self._theme_path else "Untitled SRPSS Theme",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_head": git_head_sha(self.repo_root),
            "scope": ["settings_gui", "screensaver_context_menu"],
            "tokens": tokens,
            "links": links,
        }

    def save_theme(self) -> None:
        default_dir = self.repo_root / "themes" if (self.repo_root / "themes").is_dir() else self.repo_root
        initial = str(self._theme_path or (default_dir / f"SRPSS Theme{THEME_EXTENSION}"))
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save SRPSS Theme",
            initial,
            f"SRPSS Theme (*{THEME_EXTENSION});;JSON (*.json);;All Files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if not path.suffix:
            path = path.with_suffix(THEME_EXTENSION)
        self._theme_path = path
        payload = self._theme_payload()
        payload["name"] = path.stem
        try:
            _atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        except Exception as exc:
            self._error("Save Theme failed", str(exc))
            return
        self._set_status(f"Saved full {len(self.values)}-token theme snapshot: {path.name}")

    def load_theme(self) -> None:
        initial = str(self._theme_path.parent if self._theme_path else self.repo_root)
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Load SRPSS Theme",
            initial,
            f"SRPSS Theme (*{THEME_EXTENSION} *.json);;All Files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("format") != THEME_FORMAT:
                raise ValueError("Not an SRPSS Theme file")
            if int(payload.get("version", -1)) != THEME_VERSION:
                raise ValueError(f"Unsupported theme version: {payload.get('version')}")
            raw_tokens = payload.get("tokens")
            if not isinstance(raw_tokens, Mapping):
                raise ValueError("Theme file does not contain a token mapping")

            known = 0
            unknown: list[str] = []
            missing = [tid for tid in self.values if tid not in raw_tokens]
            for tid, entry in raw_tokens.items():
                if tid not in self.values:
                    unknown.append(str(tid))
                    continue
                if not isinstance(entry, Mapping):
                    raise ValueError(f"Invalid theme token: {tid}")
                self.values[tid] = Rgba.from_json(entry.get("rgba"))
                known += 1

            self.active_links = {tid: None for tid in self.values}
            raw_links = payload.get("links", [])
            if isinstance(raw_links, list):
                for idx, group in enumerate(raw_links, start=1):
                    if not isinstance(group, list):
                        continue
                    group_id = f"loaded.link.{idx}"
                    members = [str(tid) for tid in group if str(tid) in self.values]
                    if len(members) >= 2:
                        defaults = {self.default_links.get(tid) for tid in members}
                        defaults.discard(None)
                        if len(defaults) == 1:
                            group_id = next(iter(defaults))
                        for tid in members:
                            self.active_links[tid] = group_id
            self._theme_path = path
            self._rebuild_tree(self._selected_id)
            self._refresh_editor()
            self._update_dirty_status()
            details = []
            if missing:
                details.append(f"{len(missing)} current editable token(s) were absent and kept their current values")
            if unknown:
                details.append(f"{len(unknown)} theme token(s) are unknown to this Theme Foundry version and were ignored")
            self._set_status(f"Loaded {known} token(s) from {path.name}" + (" · " + " · ".join(details) if details else ""))
            if details:
                self._warning("Theme compatibility notice", "\n".join(details))
        except Exception as exc:
            self._error("Load Theme failed", str(exc))

    # ----- source apply / launch -----------------------------------------
    def apply_to_sources(self) -> None:
        changed = [tid for tid, value in self.values.items() if self.discovery.tokens[tid].value != value]
        if not changed:
            self._set_status("No source changes to apply")
            return
        files = sorted({self.discovery.tokens[tid].source_path for tid in changed})
        message = (
            f"Apply {len(changed)} changed theme token(s) to {len(files)} canonical source file(s)?\n\n"
            + "\n".join(files)
            + "\n\nNo repository commit is performed."
        )
        if QMessageBox.question(self, "Apply Theme Foundry changes", message) != QMessageBox.StandardButton.Yes:
            return
        try:
            touched = apply_token_values(self.repo_root, self.discovery, self.values)
        except Exception as exc:
            self._error("Apply failed", str(exc))
            return

        selected = self._selected_id
        original_opened = dict(self.opened_values)
        try:
            new_discovery = discover_repo(self.repo_root)
        except Exception as exc:
            self._error(
                "Applied, but reload failed",
                f"Sources were written, but Theme Foundry could not re-read them:\n{exc}",
            )
            return
        desired = dict(self.values)
        self.discovery = new_discovery
        self.values = {tid: desired.get(tid, token.value) for tid, token in new_discovery.tokens.items()}
        self.opened_values = {tid: original_opened.get(tid, token.value) for tid, token in new_discovery.tokens.items()}
        self.default_links = {tid: token.default_link_group for tid, token in new_discovery.tokens.items()}
        self.active_links = {tid: self.active_links.get(tid, self.default_links.get(tid)) for tid in new_discovery.tokens}
        self.repo_discovery = discover_git_head(self.repo_root)
        self.repo_values = (
            {tid: token.value for tid, token in self.repo_discovery.tokens.items() if tid in new_discovery.tokens}
            if self.repo_discovery else {}
        )
        self._rebuild_tree(selected)
        self._set_status("Applied to: " + ", ".join(touched) + " · Close/relaunch Settings to see source changes")

    def launch_settings(self) -> None:
        main_py = self.repo_root / "main.py"
        if not main_py.is_file():
            self._error("Cannot launch Settings", f"main.py not found under:\n{self.repo_root}")
            return
        try:
            subprocess.Popen([sys.executable, str(main_py), "--s"], cwd=str(self.repo_root))
        except Exception as exc:
            self._error("Cannot launch Settings", str(exc))
            return
        self._set_status("Launched Settings with --s")

    # ----- utility --------------------------------------------------------
    def _refresh_tree_item(self, tid: str) -> None:
        item = self.tree_items.get(tid)
        if item is None:
            return
        state, detail = self._token_state(tid)
        item.setText(self.COL_FAV, "★" if tid in self.favorites else "☆")
        item.setText(self.COL_STATE, state)
        item.setToolTip(self.COL_STATE, detail)
        item.setText(self.COL_WORKING, self._short_value(self.values[tid]))
        repo = self.repo_values.get(tid)
        item.setText(self.COL_REPO, self._short_value(repo) if repo else "—")
        item.setText(self.COL_LINK, "🔗" if self.active_links.get(tid) else ("⛓" if self.default_links.get(tid) else ""))
        item.setToolTip(self.COL_TOKEN, self._tree_tooltip(tid))

    def _update_dirty_status(self) -> None:
        dirty = sum(1 for tid, value in self.values.items() if self.discovery.tokens[tid].value != value)
        dormant = sum(1 for tid in self.values if self.values[tid].a == 0)
        theme_name = self._theme_path.name if self._theme_path else "unsaved theme"
        self._set_status(
            f"{dirty} source change(s) pending · {theme_name} · {len(self.values)} editable tokens · "
            f"{len(self.favorites)} favorite(s) · {dormant} currently transparent"
        )

    def _short_value(self, value: Rgba | None) -> str:
        if value is None:
            return "—"
        return f"{value.hex_rgb} / {value.a}"

    def _full_value(self, value: Rgba | None) -> str:
        if value is None:
            return "—"
        return f"{value.hex_rgb} · RGBA {value.r}, {value.g}, {value.b}, {value.a} · {value.alpha_percent:.1f}% opacity"

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _warning(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def _error(self, title: str, text: str) -> None:
        QMessageBox.critical(self, title, text)


# ---------------------------------------------------------------------------
# CLI / smoke helpers
# ---------------------------------------------------------------------------

def _find_repo_root(script_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidate = script_path.resolve().parents[1]
    if (candidate / "main.py").is_file() and (candidate / "ui").is_dir():
        return candidate
    cwd = Path.cwd().resolve()
    if (cwd / "main.py").is_file() and (cwd / "ui").is_dir():
        return cwd
    return candidate


def _dump_tokens(repo_root: Path) -> int:
    result = discover_repo(repo_root)
    for token in sorted(result.tokens.values(), key=lambda t: (t.category, t.label, t.token_id)):
        print(f"{token.category:18} {token.label:48} {token.value.to_json()}  {token.token_id}")
    if result.warnings:
        print("\nWarnings:", file=sys.stderr)
        for warning in result.warnings:
            print(f"- {warning}", file=sys.stderr)
    print(f"\n{len(result.tokens)} editable token(s)")
    return 0 if result.tokens else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SRPSS Settings/context-menu colour and opacity authoring tool")
    parser.add_argument("--repo", help="SRPSS repository root (normally auto-detected when installed under tools/)")
    parser.add_argument("--dump-tokens", action="store_true", help="List discovered editable tokens without opening the GUI")
    args = parser.parse_args(argv)

    repo_root = _find_repo_root(Path(__file__), args.repo)
    if not (repo_root / "main.py").is_file():
        print(
            f"Theme Foundry could not locate an SRPSS repository at {repo_root}.\n"
            "Place it under tools/theme_foundry.py or pass --repo PATH.",
            file=sys.stderr,
        )
        return 2

    if args.dump_tokens:
        return _dump_tokens(repo_root)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_TITLE)
    icon_path = repo_root / "SRPSS.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = ThemeFoundryWindow(repo_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
