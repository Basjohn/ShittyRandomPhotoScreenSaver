"""Import-free ownership checks for Foundry navigation and deferred EB defects.

The pixel/geometry integration is covered by test_godzip_foundry_script_runner
on the operator's Windows Qt venv; this file checks the source structure when
PySide6 is unavailable on a build agent.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_foundry_right_navigation_has_its_own_reserved_row():
    source = (ROOT / 'tools/godzip_foundry.py').read_text(encoding='utf-8')
    assert 'self.primary_tab_bar = QTabBar(body)' in source
    assert 'self.primary_tab_bar.setUsesScrollButtons(True)' in source
    assert 'self.tabs.tabBar().hide()' in source
    assert 'navigation_row.addWidget(self.primary_tab_bar, 1)' in source
    assert 'navigation_row.addWidget(right_nav, 0, Qt.AlignmentFlag.AlignRight)' in source
    assert 'right_nav.setFixedWidth(right_nav_layout.sizeHint().width())' in source
    assert 'self.foundries_tab_button = QPushButton("FOUNDRIES")' in source
    assert 'self.tabs.setCornerWidget(right_nav' not in source


def test_left_and_right_foundry_navigation_share_page_authority():
    source = (ROOT / 'tools/godzip_foundry.py').read_text(encoding='utf-8')
    assert 'self.primary_tab_bar.currentChanged.connect(self._primary_nav_changed)' in source
    assert 'self.tabs.setCurrentIndex(index)' in source
    assert 'self.primary_tab_bar.blockSignals(True)' in source
    assert 'self.tabs.currentChanged.connect(self._tab_changed)' in source
    for member in ('self.run_tab', 'self.command_tab', 'self.foundries_tab'):
        assert f'self.tabs.setCurrentWidget({member})' in source


def test_live_plans_do_not_explain_archive_handoff_mechanics():
    for name in ('Current_Plan.md', 'Future_Work.md', 'Linux_Plan.md'):
        content = (ROOT / name).read_text(encoding='utf-8')
        assert not re.search(r'god.?zip|\.godzip', content, re.IGNORECASE), name
