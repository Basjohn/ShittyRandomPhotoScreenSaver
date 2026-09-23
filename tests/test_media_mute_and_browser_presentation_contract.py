"""Import-free contract for transport-colour inheritance and truthful browser fallback."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_media_mute_uses_the_transport_border_and_one_visible_frame():
    qml = (ROOT / 'rendering/quick/qml/MediaPresentation.qml').read_text(encoding='utf-8')
    start = qml.index('id: systemMuteButton')
    end = qml.index('id: systemMuteIcon', start)
    mute = qml[start:end]
    assert 'border.color: mediaRoot.mediaModel.controlsBorderColor' in mute
    assert 'systemMuteInnerBorderColor' not in mute
    # The border and glyph share the transport band's true geometric centre;
    # the former -2.0 optical nudge must not stack on the authored translation.
    assert 'anchors.verticalCenter: parent.verticalCenter' in mute
    assert 'verticalCenterOffset' not in mute
    assert 'canonicalSystemMuteHeight * fitScale' in mute
    assert '* 0.54675' in qml
    assert 'id: systemMuteTap' in qml


def test_generic_browser_fallback_cannot_mislabel_other_sites_as_spotify():
    registry = (ROOT / 'core/media/provider_registry.py').read_text(encoding='utf-8')
    model = (ROOT / 'rendering/quick/widgets/media.py').read_text(encoding='utf-8')
    browser = registry.split('"spotify_browser": MediaProviderDescriptor(', 1)[1].split(
        '"musicbee": MediaProviderDescriptor(', 1)[0]
    assert 'display_name="Browser Media (GSMTC)"' in browser
    assert 'header_name="BROWSER MEDIA"' in browser
    assert '"spotify_browser": "",' in model
    assert '"yt_music": "YouTube_Music_Icon_RGB.png"' in model
