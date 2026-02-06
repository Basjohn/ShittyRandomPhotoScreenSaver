"""About tab UI builder for the Settings Dialog.

Extracted from settings_dialog.py (M-8 refactor) to reduce monolith size.
Contains the About tab layout, header image scaling, and external link buttons.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from ui.settings_dialog import SettingsDialog

logger = get_logger(__name__)


def build_about_tab(dialog: "SettingsDialog") -> QWidget:
    """Create the About tab widget.

    Args:
        dialog: The parent SettingsDialog instance. State attributes
            (``_about_logo_source``, ``_about_shoogle_source``, etc.)
            are stored on the dialog so ``update_about_header_images``
            can rescale them responsively.

    Returns:
        The constructed QWidget for the About tab.
    """
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(15)

    # Main content card (matches ABOUTExample mockup)
    content_card = QWidget(widget)
    content_card.setObjectName("aboutContentCard")
    content_card.setStyleSheet(
        "#aboutContentCard {"
        "  background-color: #1f1f1f;"
        "  border-radius: 8px;"
        "}"
    )
    card_layout = QVBoxLayout(content_card)
    card_layout.setContentsMargins(24, 12, 24, 24)
    card_layout.setSpacing(12)

    # Header with logo and Shoogle artwork
    header_layout = QHBoxLayout()
    header_layout.setSpacing(16)

    # Store references on dialog for responsive rescaling
    dialog._about_content_card = content_card
    dialog._about_header_layout = header_layout
    dialog._about_logo_label = None
    dialog._about_shoogle_label = None
    dialog._about_logo_source = None
    dialog._about_shoogle_source = None
    dialog._about_last_card_width: int = 0

    # Resolve images directory robustly (works both in dev and frozen builds)
    try:
        images_dir = (Path(__file__).resolve().parent.parent / "images").resolve()
        if not images_dir.exists():
            alt_dir = (Path.cwd() / "images").resolve()
            if alt_dir.exists():
                images_dir = alt_dir
        logger.debug("[ABOUT] Images directory resolved to %s (exists=%s)", images_dir, images_dir.exists())
    except Exception:
        logger.debug("[SETTINGS] Exception suppressed")
        images_dir = Path.cwd() / "images"

    logo_label = QLabel()
    logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    dialog._about_logo_label = logo_label
    try:
        logo_path = images_dir / "Logo.png"
        logo_pm = QPixmap(str(logo_path))
        logger.debug("[ABOUT] Loading logo pixmap from %s (exists=%s, null=%s)", logo_path, logo_path.exists(), logo_pm.isNull())
        if not logo_pm.isNull():
            dialog._about_logo_source = logo_pm
    except Exception:
        logger.debug("[ABOUT] Failed to load Logo.png", exc_info=True)
    header_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignTop)

    shoogle_label = QLabel()
    shoogle_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    dialog._about_shoogle_label = shoogle_label
    try:
        shoogle_path = images_dir / "Shoogle300W.png"
        shoogle_pm = QPixmap(str(shoogle_path))
        logger.debug("[ABOUT] Loading Shoogle pixmap from %s (exists=%s, null=%s)", shoogle_path, shoogle_path.exists(), shoogle_pm.isNull())
        if not shoogle_pm.isNull():
            dialog._about_shoogle_source = shoogle_pm
    except Exception:
        logger.debug("[ABOUT] Failed to load Shoogle300W.png", exc_info=True)
    header_layout.addWidget(shoogle_label, 0, Qt.AlignmentFlag.AlignTop)
    header_layout.addStretch()
    card_layout.addLayout(header_layout)

    # Blurb loaded from external text file when available
    blurb_label = QLabel()
    blurb_label.setWordWrap(True)
    blurb_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    blurb_label.setStyleSheet("color: #dddddd; font-size: 12pt;")
    blurb_label.setTextFormat(Qt.TextFormat.RichText)

    default_blurb = (
        "Made for my own weird niche, shared freely for yours.<br>"
        "You can always donate to my dumbass though or buy my shitty literature."
    )
    blurb_text = default_blurb
    try:
        about_path = Path.home() / "Documents" / "AboutBlurb.txt"
        if about_path.exists():
            raw = about_path.read_text(encoding="utf-8").splitlines()
            blurb_lines: list[str] = []
            for line in raw:
                stripped = line.strip()
                if not stripped:
                    continue
                lower = stripped.lower()
                if lower.startswith("http://") or lower.startswith("https://"):
                    continue
                if "centre-aligned" in lower or "center-aligned" in lower:
                    continue
                if "then the following" in lower and "links" in lower:
                    continue
                if (stripped.startswith('"') and stripped.endswith('"')) or (
                    stripped.startswith("'") and stripped.endswith("'")
                ):
                    stripped = stripped[1:-1].strip()
                if stripped:
                    blurb_lines.append(stripped)
            if blurb_lines:
                blurb_text = "<br>".join(blurb_lines)
    except Exception as e:
        logger.debug("[SETTINGS] Exception suppressed: %s", e)

    if "You can always" in blurb_text:
        blurb_text = blurb_text.replace("You can", "You <i>can</i>", 1)

    blurb_label.setText(blurb_text)
    card_layout.addWidget(blurb_label)

    # External links row (PayPal, Goodreads, Amazon, GitHub)
    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(16)
    buttons_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def _make_link_button(text: str, url: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setStyleSheet(
            "QPushButton {"
            "  padding: 6px 18px;"
            "  font-weight: bold;"
            "  border-radius: 16px;"
            "  background-color: #2f2f2f;"
            "  color: #ffffff;"
            "  border-top: 1px solid rgba(120, 120, 120, 0.95);"
            "  border-left: 1px solid rgba(120, 120, 120, 0.95);"
            "  border-right: 2px solid rgba(0, 0, 0, 0.9);"
            "  border-bottom: 2px solid rgba(0, 0, 0, 0.95);"
            "}"
            "QPushButton:hover {"
            "  background-color: #3a3a3a;"
            "  border-top: 1px solid rgba(140, 140, 140, 0.95);"
            "  border-left: 1px solid rgba(140, 140, 140, 0.95);"
            "  border-right: 2px solid rgba(0, 0, 0, 0.95);"
            "  border-bottom: 2px solid rgba(0, 0, 0, 0.98);"
            "}"
            "QPushButton:pressed {"
            "  background-color: #262626;"
            "  border-top: 1px solid rgba(80, 80, 80, 0.9);"
            "  border-left: 1px solid rgba(80, 80, 80, 0.9);"
            "  border-right: 1px solid rgba(0, 0, 0, 0.9);"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.9);"
            "  margin-top: 1px;"
            "  margin-left: 1px;"
            "}"
        )

        def _open() -> None:
            try:
                QDesktopServices.openUrl(QUrl(url))
            except Exception:
                logger.debug("[SETTINGS] Exception suppressed")

        btn.clicked.connect(_open)
        return btn

    buttons_row.addWidget(_make_link_button("PAYPAL", "https://www.paypal.com/donate/?business=UBZJY8KHKKLGC&no_recurring=0&item_name=Why+are+you+doing+this?+Are+you+drunk?+&currency_code=USD"))
    buttons_row.addWidget(_make_link_button("GOODREADS", "https://www.goodreads.com/book/show/25006763-usu"))
    buttons_row.addWidget(_make_link_button("AMAZON", "https://www.amazon.com/Usu-Jayde-Ver-Elst-ebook/dp/B00V8A5K7Y"))
    buttons_row.addWidget(_make_link_button("GITHUB", "https://github.com/Basjohn?tab=repositories"))
    card_layout.addLayout(buttons_row)

    # Hotkeys section beneath links
    hotkeys_label = QLabel(
        "<p><b>Hotkeys While Running:</b></p>"
        "<p>"
        "<b>Z</b>  - Go back to previous image<br>"
        "<b>X</b>  - Go forward to next image<br>"
        "<b>C</b>  - Cycle transition modes (Crossfade   Slide   Wipe   Diffuse   Block Flip)<br>"
        "<b>S</b>  - Stop screensaver and open Settings<br>"
        "<b>ESC</b> - Exit screensaver<br>"
        "<b>Ctrl (HOLD)</b> - Temporary interaction mode (widgets clickable without exiting)<br>"
        "<b>Mouse Click/Any Other Key</b> - Exit screensaver"
        "</p>"
    )
    hotkeys_label.setWordWrap(True)
    hotkeys_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    hotkeys_label.setStyleSheet("color: #cccccc; margin-top: 16px;")
    hotkeys_label.setOpenExternalLinks(False)
    card_layout.addWidget(hotkeys_label)

    layout.addWidget(content_card)
    layout.addStretch()

    # Reset / Import / Export buttons (bottom row)
    button_row = QHBoxLayout()
    dialog.reset_defaults_btn = QPushButton("Reset To Defaults")
    dialog.reset_defaults_btn.setObjectName("resetDefaultsButton")
    dialog.reset_defaults_btn.setFixedHeight(24)
    dialog.reset_defaults_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
    dialog.reset_defaults_btn.clicked.connect(dialog._on_reset_to_defaults_clicked)
    button_row.addWidget(dialog.reset_defaults_btn)

    button_row.addStretch()

    dialog.import_settings_btn = QPushButton("Import Settings…")
    dialog.import_settings_btn.setFixedHeight(24)
    dialog.import_settings_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
    dialog.import_settings_btn.clicked.connect(dialog._on_import_settings_clicked)
    button_row.addWidget(dialog.import_settings_btn)

    dialog.export_settings_btn = QPushButton("Export Settings…")
    dialog.export_settings_btn.setFixedHeight(24)
    dialog.export_settings_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
    dialog.export_settings_btn.clicked.connect(dialog._on_export_settings_clicked)
    button_row.addWidget(dialog.export_settings_btn)

    # More options button (context menu)
    dialog.more_options_btn = QPushButton("⋮")
    dialog.more_options_btn.setFixedSize(24, 24)
    dialog.more_options_btn.setStyleSheet("""
        QPushButton {
            font-size: 14px;
            font-weight: bold;
            padding: 0;
            border: 1px solid rgba(80, 80, 90, 150);
            border-radius: 4px;
            background-color: rgba(40, 40, 45, 200);
            color: rgba(200, 200, 210, 220);
        }
        QPushButton:hover {
            background-color: rgba(60, 60, 70, 220);
        }
    """)
    dialog.more_options_btn.setToolTip("More options")
    dialog.more_options_btn.clicked.connect(dialog._show_more_options_menu)
    button_row.addWidget(dialog.more_options_btn)
    layout.addLayout(button_row)

    dialog.reset_notice_label = QLabel("Settings reverted to defaults!")
    dialog.reset_notice_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    dialog.reset_notice_label.setStyleSheet(
        "color: #ffffff; font-size: 11px; padding: 4px 10px; "
        "background-color: rgba(16, 16, 16, 230); border-radius: 6px;"
    )
    dialog.reset_notice_label.setVisible(False)
    layout.addWidget(dialog.reset_notice_label)

    return widget


def update_about_header_images(dialog: "SettingsDialog") -> None:
    """Scale About header images responsively based on dialog width.

    The logo and fish artwork are always scaled down from their source
    resolution using smooth, high-DPI aware transforms and never
    upscaled beyond 100% size. When the settings dialog is narrow the
    images shrink together so they never clip or overlap.

    Args:
        dialog: The SettingsDialog instance holding the source pixmaps.
    """
    card = getattr(dialog, "_about_content_card", None)
    header_layout = getattr(dialog, "_about_header_layout", None)
    logo_label = getattr(dialog, "_about_logo_label", None)
    shoogle_label = getattr(dialog, "_about_shoogle_label", None)
    logo_src = getattr(dialog, "_about_logo_source", None)
    shoogle_src = getattr(dialog, "_about_shoogle_source", None)

    if (
        card is None
        or header_layout is None
        or logo_label is None
        or shoogle_label is None
        or logo_src is None
        or logo_src.isNull()
        or shoogle_src is None
        or shoogle_src.isNull()
    ):
        return

    current_width = card.width()
    if current_width <= 0:
        return

    last_width = getattr(dialog, "_about_last_card_width", 0)
    if last_width and abs(current_width - last_width) < 12:
        return
    dialog._about_last_card_width = current_width

    available = current_width - card.contentsMargins().left() - card.contentsMargins().right()
    if available <= 0:
        return

    spacing = header_layout.spacing()
    total_w = logo_src.width() + shoogle_src.width()
    if total_w <= 0 or available <= spacing + 10:
        scale = 1.0
    else:
        scale = (available - spacing) / float(total_w)
        scale = max(0.5, min(2.0, scale))

    try:
        dpr = float(dialog.devicePixelRatioF())
    except Exception:
        logger.debug("[SETTINGS] Exception suppressed")
        dpr = 1.0
    if dpr < 1.0:
        dpr = 1.0

    def _apply(src: QPixmap, label: QLabel, *, y_offset: int = 0) -> None:
        if src is None or src.isNull():
            return

        target_w = max(1, int(round(src.width() * scale * dpr)))
        target_h = max(1, int(round(src.height() * scale * dpr)))

        scaled = src.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if dpr != 1.0:
            try:
                scaled.setDevicePixelRatio(dpr)
            except Exception:
                logger.debug("[SETTINGS] Exception suppressed")

        label.setPixmap(scaled)

        logical_w = max(1, int(round(scaled.width() / dpr)))
        logical_h = max(1, int(round(scaled.height() / dpr)))
        label.setMinimumSize(logical_w, logical_h)
        label.setMaximumSize(logical_w, logical_h)
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        if y_offset != 0:
            label.setContentsMargins(0, max(0, y_offset), 0, 0)
        else:
            label.setContentsMargins(0, 0, 0, 0)

    _apply(logo_src, logo_label, y_offset=5)
    _apply(shoogle_src, shoogle_label, y_offset=0)
