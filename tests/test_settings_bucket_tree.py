"""Native layout/paint falsifiers for shared Settings hierarchy rails."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from ui.tabs.shared_styles import (
    add_aligned_row_widget, apply_shared_label_style, build_bucket_toggle,
)
from ui.widgets.bucket_tree import BUCKET_CHILD_INDENT, BucketTreeBody


def _settle(app):
    app.processEvents()
    app.processEvents()


def _anchor(widget, body):
    origin = widget.mapTo(body, QPoint())
    return origin.x(), origin.y() + widget.height() / 2.0


def _points(body):
    return tuple((point.x(), point.y()) for point in body.branch_anchors())


def _assert_painted_rail_ends_at(body, y):
    """Read native pixels: decoration exists, but no trunk overruns its leaf."""
    image = body.grab().toImage()
    dpr = image.devicePixelRatio()
    x = body.layout().contentsMargins().left() / 2.0
    def pixel(px, py):
        return image.pixelColor(round(px * dpr), round(py * dpr))
    assert pixel(x, 3) != pixel(x + 4, 3)
    assert pixel(x, y + 5) == pixel(x + 4, y + 5)


def test_nested_bucket_rails_stop_at_headers_and_visible_rows(qt_app):
    host = QWidget()
    layout = QVBoxLayout(host)
    _parent, body, children = build_bucket_toggle(layout, "Parent", expanded=True)
    top = QLabel("Leading control")
    children.addWidget(top)
    child, subtree, descendants = build_bucket_toggle(children, "Nested", expanded=True)
    leaf = QLabel("Nested control")
    descendants.addWidget(leaf)
    # A visibility/grouping QWidget is not a second hierarchy owner. Its
    # vertical children remain peers, including when it holds nested buckets.
    wrapper = QWidget()
    wrapped_rows = QVBoxLayout(wrapper)
    wrapped_rows.setContentsMargins(0, 0, 0, 0)
    last = QLabel("Conditional last control")
    wrapped_rows.addWidget(last)
    helper = QLabel("Nested disclosure explanation")
    apply_shared_label_style(helper, "ADV_HELPER_LABEL_STYLE")
    wrapped_rows.addWidget(helper)
    children.addWidget(wrapper)
    host.resize(600, 420)
    host.show()
    try:
        _settle(qt_app)
        assert isinstance(body, BucketTreeBody)
        assert _points(body) == (_anchor(top, body), _anchor(child, body), _anchor(last, body))
        assert _points(subtree) == (_anchor(leaf, subtree),)
        _assert_painted_rail_ends_at(body, _anchor(last, body)[1])
        # Collapsing the nested branch changes its own descendants, never the
        # parent's logical children or its terminal header/row endpoint.
        child.setChecked(False)
        last.hide()
        _settle(qt_app)
        assert subtree.isHidden()
        assert _points(body) == (_anchor(top, body), _anchor(child, body))
        _assert_painted_rail_ends_at(body, _anchor(child, body)[1])
        last.show()
        _settle(qt_app)
        assert _points(body)[-1] == _anchor(last, body)
    finally:
        host.close()
        host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_dynamic_rows_resize_and_sibling_control_columns_share_one_gutter(qt_app):
    host = QWidget()
    layout = QVBoxLayout(host)
    toggle, body, children = build_bucket_toggle(layout, "Lazy", expanded=False)
    assert not children.count()  # rail construction never builds controls
    toggle.setChecked(True)
    labels = []
    sliders = []
    for caption in ("First:", "Second:"):
        row, content, label = add_aligned_row_widget(children, caption, label_width=110)
        slider = QSlider(Qt.Orientation.Horizontal)
        content.addWidget(slider)
        labels.append(label)
        sliders.append(slider)
    host.resize(600, 320)
    host.show()
    try:
        _settle(qt_app)
        for width in (780, 480, 670):
            host.resize(width, 320)
            _settle(qt_app)
            assert _points(body) == tuple(_anchor(label, body) for label in labels)
            assert labels[0].mapTo(body, QPoint()).x() == BUCKET_CHILD_INDENT
            assert sliders[0].mapTo(body, QPoint()).x() == sliders[1].mapTo(body, QPoint()).x()
            # Exercise actual native Qt paint at fractional and integer DPR,
            # without changing global environment or application DPI state.
            from PySide6.QtGui import QPixmap
            for dpr in (1.0, 1.5, 2.0):
                pixmap = QPixmap(body.size() * dpr)
                pixmap.setDevicePixelRatio(dpr)
                body.render(pixmap)
                assert not pixmap.isNull()
        toggle.setChecked(False)
        assert body.isHidden()
        toggle.setChecked(True)
        _settle(qt_app)
        assert children.count() == 2
        assert _points(body) == tuple(_anchor(label, body) for label in labels)
    finally:
        host.close()
        host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_control_without_label_connects_to_control_not_alignment_placeholder(qt_app):
    host = QWidget()
    _toggle, body, children = build_bucket_toggle(QVBoxLayout(host), "Controls", expanded=True)
    row = QHBoxLayout()
    placeholder = QLabel("")
    placeholder.setFixedWidth(120)
    checkbox = QCheckBox("Use recommended value")
    row.addWidget(placeholder)
    row.addWidget(checkbox)
    children.addLayout(row)
    host.show()
    try:
        _settle(qt_app)
        assert _points(body) == (_anchor(checkbox, body),)
    finally:
        host.close()
        host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_explanatory_and_live_stack_captions_do_not_extend_parent_rail(qt_app, monkeypatch):
    """Cross the real shared status owner; a trailing caption is not a leaf."""
    from types import SimpleNamespace
    from ui.tabs import widgets_tab

    host = QWidget()
    _parent, body, children = build_bucket_toggle(QVBoxLayout(host), "Parent", expanded=True)
    intro = QLabel("Explanatory introduction")
    apply_shared_label_style(intro, "INFO_LABEL_STYLE")
    children.addWidget(intro)
    child, _subtree, _descendants = build_bucket_toggle(children, "Last relevant child")
    children.addStretch(1)
    status = QLabel()
    children.addWidget(status)
    target = SimpleNamespace(status_label=status, widget_type_key=widgets_tab.WidgetType.CLOCK.value,
                             position_value="Bottom Left", monitor_value="ALL")
    monkeypatch.setattr(widgets_tab, "collect_widget_stack_status_targets", lambda owner: (target,))
    monkeypatch.setattr(widgets_tab, "get_position_status_for_widget",
                        lambda *args, **kwargs: (True, "Live contextual status"))
    owner = SimpleNamespace(_build_current_widgets_config=lambda: {}, _widget_defaults={})
    widgets_tab.WidgetsTab._update_stack_status(owner)
    assert status.text() == "Live contextual status"
    assert status.property("settingsAnnotation") is True
    host.resize(600, 550)
    host.show()
    try:
        _settle(qt_app)
        assert status.mapTo(body, QPoint()).y() > child.mapTo(body, QPoint()).y() + 100
        assert _points(body) == (_anchor(child, body),)
        _assert_painted_rail_ends_at(body, _anchor(child, body)[1])
        # Removing both captions does not change the node count or label/control
        # geometry policy; Qt alone reflows the remaining header.
        intro.hide()
        status.hide()
        _settle(qt_app)
        assert _points(body) == (_anchor(child, body),)
    finally:
        host.close()
        host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
