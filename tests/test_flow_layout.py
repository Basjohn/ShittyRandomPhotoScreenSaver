"""Responsive FlowLayout invariants (Phase E2 §7).

Deterministic, width-driven assertions (no exact pixel overfitting): the layout
wraps to more rows as width shrinks, packs more columns as width grows, preserves
child order, and lets hidden children collapse so remaining items reflow.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from ui.flow_layout import FlowLayout


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _host(n: int, *, item_width: int = 100, item_height: int = 30):
    host = QWidget()
    flow = FlowLayout(host, h_spacing=10, v_spacing=10)
    buttons = []
    for i in range(n):
        b = QPushButton(f"b{i}")
        b.setFixedSize(item_width, item_height)
        flow.addWidget(b)
        buttons.append(b)
    return host, flow, buttons


def test_narrow_wraps_taller_than_wide(qapp):
    _host_w, flow, _b = _host(8)
    wide = flow.heightForWidth(2000)
    narrow = flow.heightForWidth(120)
    assert narrow > wide  # fewer columns when narrow -> more rows -> taller


def test_wide_fits_single_row(qapp):
    _host_w, flow, _b = _host(6, item_height=30)
    # Very wide: all six fit on one row (height ~ one item + margins).
    assert flow.heightForWidth(5000) <= 30 + 12  # one row, small slack


def test_more_columns_when_wider(qapp):
    # A width fitting ~2 columns is taller than one fitting ~4 columns.
    _host_w, flow, _b = _host(8, item_width=100)
    two_col = flow.heightForWidth(230)   # ~2 per row
    four_col = flow.heightForWidth(450)  # ~4 per row
    assert two_col > four_col


def test_hidden_items_collapse(qapp):
    host, flow, buttons = _host(8, item_width=100)
    before = flow.heightForWidth(230)
    for b in buttons[4:]:
        b.setVisible(False)
    after = flow.heightForWidth(230)
    assert after <= before  # hidden items free rows


def test_child_order_preserved(qapp):
    _host_w, flow, buttons = _host(5)
    ordered = [flow.itemAt(i).widget() for i in range(flow.count())]
    assert ordered == buttons
