"""Projection choice has one persisted owner; hiding FOV never changes its authored value."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_settings import spec_control
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
from core.settings import visualizer_presets as vp

KEY='extruded_bubble_camera_projection'
FOV='extruded_bubble_camera_fov'


def test_missing_projection_preserves_existing_perspective_and_choice_is_eb_only():
    assert require_canonical_default('widgets.spotify_visualizer.'+KEY)=='Perspective'
    assert SpotifyVisualizerSettings.from_mapping({},apply_preset_overlay=False).extruded_bubble_camera_projection=='Perspective'
    control=spec_control(KEY)
    assert control.choices==('Perspective','Orthographic')
    assert control.admit('unknown','Perspective')=='Perspective'
    assert spec_control('shockwave_grid_camera_projection') is None


@pytest.mark.parametrize('projection',('Perspective','Orthographic'))
def test_model_snapshot_and_imported_preset_preserve_projection_and_hidden_fov(projection,monkeypatch):
    raw={KEY:projection,FOV:53.}
    model=SpotifyVisualizerSettings.from_mapping(raw,apply_preset_overlay=False)
    serialized=asdict(model)
    assert serialized[KEY]==projection and serialized[FOV]==53.
    saved=model.to_dict()
    assert saved['widgets.spotify_visualizer.'+KEY]==projection
    assert saved['widgets.spotify_visualizer.'+FOV]==53.
    assert normalize_visualizer_section_mapping(raw,apply_preset_overlay=False)[KEY]==projection
    imported=vp._parse_preset_payload(Path('preset_1_projection.json'),
        {'name':'Projection witness','preset_index':0,'settings':raw},'extruded_bubble')
    assert imported is not None
    _,preset=imported
    assert preset.settings[KEY]==projection and preset.settings[FOV]==53.
    with monkeypatch.context() as scoped:
        scoped.setattr(vp,'_PRESETS',{**vp._PRESETS,'extruded_bubble':[
            preset,vp.VisualizerPreset('Custom','test-owned',{},is_custom=True)]})
        applied=vp.apply_preset_to_config('extruded_bubble',0,{KEY:'Perspective',FOV:37.})
        assert applied[KEY]==projection and applied[FOV]==53.


def test_lazy_camera_choice_hides_fov_without_resetting_it(qt_app,tmp_path):
    from PySide6.QtCore import QCoreApplication,QEvent
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from ui.tabs.visualizers_tab import VisualizersTab
    from ui.tabs.media.extruded_bubble_settings_binding import load_extruded_bubble_mode_settings,collect_extruded_bubble_mode_settings
    from tests.test_extruded_bubble_lazy_bucket_ui import toggle_bucket
    config=deepcopy(require_canonical_default('widgets.spotify_visualizer'))
    config.update(mode='extruded_bubble',preset_extruded_bubble=vp.get_custom_preset_index('extruded_bubble'),
        mode_activation=build_visualizer_mode_activation(['extruded_bubble']),**{KEY:'Orthographic',FOV:53.})
    manager=SettingsManager(application='ProjectionChoiceWitness',storage_base_dir=tmp_path)
    manager.set('widgets',{'spotify_visualizer':config})
    tab=VisualizersTab(manager);tab._select_mode_page('extruded_bubble')
    try:
        load_extruded_bubble_mode_settings(tab,config)
        assert not hasattr(tab,KEY)
        values=collect_extruded_bubble_mode_settings(tab)
        assert values[KEY]=='Orthographic' and values[FOV]==53.
        toggle_bucket(tab,'camera')
        chooser=getattr(tab,KEY);row=tab._extruded_bubble_rows[FOV]
        assert chooser.model().item(0).isEnabled()
        assert not chooser.model().item(1).isEnabled()
        assert 'Deferred' in chooser.model().item(1).toolTip()
        assert chooser.currentText()=='Orthographic' and row.isHidden()
        chooser.setCurrentText('Perspective')
        assert not row.isHidden() and getattr(tab,FOV).value()==53
        chooser.setCurrentText('Orthographic')
        assert row.isHidden()
        values=collect_extruded_bubble_mode_settings(tab)
        assert values[KEY]=='Orthographic' and values[FOV]==53.
        # Hydration of an already built bucket follows the same authority.
        load_extruded_bubble_mode_settings(tab,{**config,KEY:'Perspective',FOV:41.})
        assert chooser.currentText()=='Perspective' and not row.isHidden()
        assert collect_extruded_bubble_mode_settings(tab)[FOV]==41.
        tab.flush_pending_changes()
        chooser.setCurrentText('Orthographic');tab.flush_pending_changes()
        assert manager.get('widgets.spotify_visualizer.'+KEY)=='Orthographic'
        assert manager.get('widgets.spotify_visualizer.'+FOV)==41.
        tab._load_settings()
        assert chooser.currentText()=='Orthographic' and row.isHidden()
        # Existing experimental files round-trip, but normal authoring cannot
        # enter the deferred option (including keyboard navigation).
        chooser.setCurrentText('Perspective');tab.flush_pending_changes()
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.keyClick(chooser,Qt.Key.Key_Down)
        assert chooser.currentText()=='Perspective' and not row.isHidden()
        tab.resize(1100,950);tab.show();qt_app.processEvents()
        from PySide6.QtCore import QEventLoop,QTimer
        settled=QEventLoop();QTimer.singleShot(350,settled.quit);settled.exec()
        from PySide6.QtWidgets import QScrollArea
        parent=chooser.parentWidget()
        while parent is not None:
            if isinstance(parent,QScrollArea):parent.ensureWidgetVisible(chooser,40,180)
            parent=parent.parentWidget()
        qt_app.processEvents()
        assert chooser.isVisibleTo(tab) and chooser.parentWidget().height()>0
        assert tab.grab().save(str(tmp_path/'camera_projection_native.png'))
        chooser.showPopup();qt_app.processEvents()
        assert chooser.view().grab().save(str(tmp_path/'camera_projection_options_native.png'))
        chooser.hidePopup()
    finally:
        tab._flush_pending_visualizer_save();tab.close();tab.deleteLater()
        QCoreApplication.sendPostedEvents(tab,QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.)
