"""AC-01: the Settings tabs and pills come from one descriptor registry (``ui/settings_tabs.py``) with profile gating.

Drives the real SettingsDialog on a test-owned profile with image sources configured (so no "No Image Sources" prompt
or Guided Setup can arise) and never shows it. Membership, labels and pill vocabularies are read from the registry,
never from a hand list; no authored preset or value is asserted.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLineEdit

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, iter_visualizer_mode_descriptors
from core.threading.manager import ThreadManager

pytestmark = pytest.mark.qt

_UI_BUCKET_KEYS = (
    "ui.widget_bucket_states", "ui.gmail_bucket_states", "ui.visualizer_bucket_states",
    "ui.visualizer_tech_bucket_states", "ui.visualizer_adv_states", "ui.visualizer_tech_states",
    "ui.basic_bucket_path",
)


@pytest.fixture
def manager(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="tab_registry", storage_base_dir=tmp_path)
    modes = [d.mode_id for d in iter_visualizer_mode_descriptors()]
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": modes[0],
                   "mode_activation": build_visualizer_mode_activation(modes)})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)


def _dialog(manager):
    from ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    return dialog


def _destroy(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _current_key(dialog):
    return dialog._tab_key_for_index(dialog.content_stack.currentIndex())


def _sidebar_labels(dialog):
    from ui.settings_dialog import TabButton
    return sorted(button.text() for button in dialog.findChildren(TabButton))


def _pill_samples():
    """(tab key, view state) samples covering every pill vocabulary the registry declares."""
    from rendering.transition_settings import iter_transition_settings
    from ui.settings_tabs import SETTINGS_TAB_DESCRIPTORS
    transition = next(spec for spec in iter_transition_settings() if spec.section)
    mode = next(iter(iter_visualizer_mode_descriptors())).mode_id
    samples = [(d.key, {}) for d in SETTINGS_TAB_DESCRIPTORS]
    samples += [("widgets", {"subtab_id": "steam"}), ("visualizers", {"page": "mode", "mode_id": mode}),
                ("visualizers", {"page": "setup"}), ("transitions", {"pill": transition.name})]
    return samples


def test_the_dialog_derives_tabs_builders_warm_list_and_labels_from_the_registry(manager):
    from ui.settings_tabs import SETTINGS_TAB_DESCRIPTORS
    dialog = _dialog(manager)
    keys = [d.key for d in SETTINGS_TAB_DESCRIPTORS]
    assert dialog._tab_keys == keys
    assert list(dialog._tab_builders) == keys
    assert set(dialog._background_warm_tab_keys) == {d.key for d in SETTINGS_TAB_DESCRIPTORS if d.warm_in_background}
    assert _sidebar_labels(dialog) == sorted(d.label for d in SETTINGS_TAB_DESCRIPTORS)
    assert [dialog._tab_button_by_key[k] for k in keys] == dialog.tab_buttons
    # Tab bodies stay lazy: only the initial page is built synchronously.
    assert [k for k in keys if dialog.__dict__.get(f"{k}_tab") is not None] == [_current_key(dialog)]
    _destroy(dialog)


@pytest.mark.parametrize("key, view", _pill_samples())
def test_initial_and_reload_pills_agree_and_round_trip_the_projection(manager, monkeypatch, key, view):
    """Both pill chains are the descriptor's ``pill_of``: construction and a reload project the same (tab, pill),
    and the remembered editing path of that pill survives both projections."""
    import core.settings.ui_bucket_state as bucket_state
    from ui.settings_tabs import settings_tab_descriptor

    pill = settings_tab_descriptor(key).pill_of(view)
    if key == "sources":
        manager.set("ui.basic_bucket_path", "sources:folders")
    elif key == "transitions" and pill:
        manager.set("ui.basic_bucket_path", "transitions:" + pill)
    manager.set("ui.last_tab_key", key)
    manager.set("ui.tab_state", {key: {"view_state": dict(view)}} if view else {})

    calls = []
    original = bucket_state.project_settings_bucket_context
    monkeypatch.setattr(bucket_state, "project_settings_bucket_context",
                        lambda settings, tab, pill=None: (calls.append((tab, pill)), original(settings, tab, pill))[1])
    dialog = _dialog(manager)
    assert _current_key(dialog) == key
    assert calls == [(key, pill)]
    after_initial = {name: deepcopy(manager.get(name)) for name in _UI_BUCKET_KEYS}
    if key in ("sources", "transitions") and (key == "sources" or pill):
        assert manager.get("ui.basic_bucket_path") == (f"{key}:folders" if key == "sources" else f"{key}:{pill}")

    current = dialog.content_stack.currentWidget()
    monkeypatch.setattr(current, "get_view_state", lambda: dict(view), raising=False)
    calls.clear()
    dialog._reload_all_tab_settings()
    assert calls == [(key, pill)]
    assert {name: manager.get(name) for name in _UI_BUCKET_KEYS} == after_initial
    _destroy(dialog)


def _registry_without(monkeypatch, hidden_key, predicate=lambda _profile: False):
    import ui.settings_tabs as settings_tabs
    patched = tuple(replace(d, available=predicate) if d.key == hidden_key else d
                    for d in settings_tabs.SETTINGS_TAB_DESCRIPTORS)
    monkeypatch.setattr(settings_tabs, "SETTINGS_TAB_DESCRIPTORS", patched)
    return next(d for d in patched if d.key == hidden_key)


def test_an_unavailable_tab_is_absent_and_never_shifts_the_remembered_tab(manager, monkeypatch):
    import ui.settings_tabs as settings_tabs
    keys = [d.key for d in settings_tabs.SETTINGS_TAB_DESCRIPTORS]
    hidden = _registry_without(monkeypatch, "layout")
    remembered = keys[keys.index("layout") + 2]          # a tab after the hidden one: positions would shift it
    manager.set("ui.last_tab_key", remembered)

    dialog = _dialog(manager)
    assert hidden.key not in dialog._tab_keys
    assert hidden.label not in _sidebar_labels(dialog)
    assert dialog.content_stack.count() == len(dialog._tab_keys) == len(keys) - 1
    names = {dialog.content_stack.widget(i).objectName() for i in range(dialog.content_stack.count())}
    assert f"{hidden.key}_placeholder" not in names
    assert not hasattr(dialog, f"{hidden.key}_tab_btn")
    with pytest.raises(AttributeError):
        getattr(dialog, f"{hidden.key}_tab")
    assert _current_key(dialog) == remembered
    assert manager.get("ui.last_tab_key") == remembered
    _destroy(dialog)

    # The remembered tab itself is hidden in this profile: Settings opens on its first tab and keeps the memory.
    manager.set("ui.last_tab_key", hidden.key)
    dialog = _dialog(manager)
    assert _current_key(dialog) == dialog._tab_keys[0]
    assert manager.get("ui.last_tab_key") == hidden.key
    # An explicit switch is a new memory.
    dialog._switch_tab(dialog._tab_index_for_key(remembered), animate=False)
    assert manager.get("ui.last_tab_key") == remembered
    _destroy(dialog)


def test_availability_reads_the_one_product_identity_predicate(manager, monkeypatch):
    import core.mc as mc
    hidden = _registry_without(monkeypatch, "scene3d", predicate=lambda profile: not profile.mc)
    monkeypatch.setattr(mc, "is_mc_build", lambda: True)
    dialog = _dialog(manager)
    assert hidden.key not in dialog._tab_keys
    _destroy(dialog)
    monkeypatch.setattr(mc, "is_mc_build", lambda: False)
    dialog = _dialog(manager)
    assert hidden.key in dialog._tab_keys
    _destroy(dialog)


def test_config_mode_settings_owns_the_one_helper_thread_manager(manager, monkeypatch):
    """A-14: with no app-shared ThreadManager (CONFIG mode), the dialog registers one helper manager for its life; the
    helper sites look it up instead of building their own, and it is gone after the dialog is destroyed."""
    from core.gmail.gmail_backend import GmailBackend
    from core.gmail.gmail_oauth import GmailOAuthManager
    from ui.tabs import widgets_tab_defaults, widgets_tab_feeds, widgets_tab_gmail, widgets_tab_steam
    from ui.widgets.geocode_completer import GeocodeCompleter

    monkeypatch.setattr(ThreadManager, "_app_shared_manager", None)
    created = []
    factory = ThreadManager.create_helper_manager.__func__
    monkeypatch.setattr(ThreadManager, "create_helper_manager",
                        classmethod(lambda cls, **kw: created.append(factory(cls, **kw)) or created[-1]))

    dialog = _dialog(manager)
    tab = dialog.widgets_tab
    completer = GeocodeCompleter(QLineEdit(tab))
    oauth = GmailOAuthManager()
    managers = [
        widgets_tab_defaults._get_cache_thread_manager(tab),
        widgets_tab_feeds._get_feed_thread_manager(tab),
        widgets_tab_gmail._get_gmail_thread_manager(tab),
        widgets_tab_steam._get_steam_thread_manager(tab),
        oauth._get_thread_manager(),
        GmailBackend(oauth_manager=oauth).get_bootstrap_thread_manager(),
    ]
    assert len(created) <= 1
    shared = ThreadManager.get_app_shared()
    assert shared is not None and all(m is shared for m in managers)
    assert completer is not None

    _destroy(dialog)
    assert ThreadManager.get_app_shared() is None
    assert all(getattr(m, "_shutdown", False) for m in created)


def test_runtime_settings_borrows_the_registered_manager(manager, monkeypatch):
    """A-14 negative control: under a runtime the app-shared manager already exists; Settings creates none and leaves
    the registration alone when it dies."""
    runtime = ThreadManager.create_helper_manager()
    monkeypatch.setattr(ThreadManager, "_app_shared_manager", runtime)
    created = []
    monkeypatch.setattr(ThreadManager, "create_helper_manager",
                        classmethod(lambda cls, **kw: created.append(kw) or runtime))
    dialog = _dialog(manager)
    _destroy(dialog)
    assert created == []
    assert ThreadManager.get_app_shared() is runtime
    runtime.shutdown(wait=True)
