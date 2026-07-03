from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import pytest

from core.settings.settings_manager import SettingsManager
from core.steam.credentials import (
    SteamCredentialError,
    SteamCredentialPayload,
    disconnect_account,
    derive_profile_cache_key,
    get_profile_cache_dir_for_credentials,
    get_storage_status,
    load_credentials,
    redact_mapping,
    save_credentials,
    strip_secret_fields,
    validate_credential_input,
)


SENTINEL_KEY = "fake_steam_api_key_do_not_export_12345"
SENTINEL_PROFILE = "76561198000000000"


def _make_manager(tmp_path: Path) -> SettingsManager:
    return SettingsManager(
        organization="TestOrg",
        application=f"SteamCredentialTest_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path / uuid.uuid4().hex,
    )


def test_steam_credentials_require_dpapi_output_and_leave_no_file(tmp_path: Path) -> None:
    credential_path = tmp_path / "credentials.bin"
    meta_path = tmp_path / "credential_meta.json"
    credential = SteamCredentialPayload(
        api_key=SENTINEL_KEY,
        profile_identifier=SENTINEL_PROFILE,
    )

    with pytest.raises(SteamCredentialError):
        save_credentials(
            credential,
            encrypt_func=lambda payload: b"plain::" + payload,
            credentials_path=credential_path,
            meta_path=meta_path,
        )

    assert not credential_path.exists()
    assert not meta_path.exists()


def test_steam_credentials_roundtrip_and_metadata_do_not_leak_secret(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    credential_path = tmp_path / "credentials.bin"
    meta_path = tmp_path / "credential_meta.json"
    credential = SteamCredentialPayload(
        api_key=SENTINEL_KEY,
        profile_identifier=SENTINEL_PROFILE,
    )
    encrypted_payload: dict[str, bytes] = {}

    def _fake_encrypt(payload: bytes) -> bytes:
        encrypted_payload["payload"] = payload
        return b"dpapi::opaque-test-blob"

    def _fake_decrypt(blob: bytes) -> bytes:
        assert blob == b"dpapi::opaque-test-blob"
        return encrypted_payload["payload"]

    caplog.set_level(logging.INFO)
    save_credentials(
        credential,
        encrypt_func=_fake_encrypt,
        credentials_path=credential_path,
        meta_path=meta_path,
    )

    assert credential_path.read_bytes().startswith(b"dpapi::")
    assert SENTINEL_KEY.encode("utf-8") not in credential_path.read_bytes()
    loaded = load_credentials(
        decrypt_func=_fake_decrypt,
        credentials_path=credential_path,
    )

    assert loaded is not None
    assert loaded.api_key == credential.api_key
    assert loaded.profile_identifier == credential.profile_identifier
    assert loaded.provider_mode == credential.provider_mode
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    meta_text = meta_path.read_text(encoding="utf-8")
    assert SENTINEL_KEY not in meta_text
    assert SENTINEL_PROFILE not in meta_text
    assert "profile_cache_key" in json.loads(meta_text)
    assert SENTINEL_KEY not in caplog.text
    assert SENTINEL_PROFILE not in caplog.text


def test_steam_credentials_reject_plaintext_file_on_load(tmp_path: Path) -> None:
    credential_path = tmp_path / "credentials.bin"
    credential_path.write_bytes(b"plain::{}")

    with pytest.raises(SteamCredentialError):
        load_credentials(credentials_path=credential_path)


def test_steam_profile_cache_key_is_opaque_and_stable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from core.settings import storage_paths

    storage_paths.reset_module_cache()
    credential = SteamCredentialPayload(
        api_key=SENTINEL_KEY,
        profile_identifier=SENTINEL_PROFILE,
    )

    cache_key = derive_profile_cache_key(SENTINEL_PROFILE)
    cache_dir = get_profile_cache_dir_for_credentials(credential)

    assert cache_key.startswith("profile_")
    assert SENTINEL_PROFILE not in cache_key
    assert SENTINEL_PROFILE not in str(cache_dir)
    assert cache_dir.name == cache_key


def test_steam_redaction_strips_only_steam_secret_fields() -> None:
    payload = {
        "widgets": {
            "steam": {
                "api_key": SENTINEL_KEY,
                "profile_identifier": SENTINEL_PROFILE,
                "safe": True,
            },
            "other": {
                "api_key": "not_steam_and_should_remain",
            },
        },
        "steam_api_key": SENTINEL_KEY,
    }

    cleaned, removed = strip_secret_fields(payload)
    redacted = redact_mapping(payload)

    assert removed == 3
    assert cleaned["widgets"]["steam"] == {"safe": True}
    assert cleaned["widgets"]["other"]["api_key"] == "not_steam_and_should_remain"
    assert "steam_api_key" not in cleaned
    assert redacted["widgets"]["steam"]["api_key"] == "<redacted>"
    assert redacted["widgets"]["other"]["api_key"] == "not_steam_and_should_remain"


def test_sst_export_and_import_strip_injected_steam_secret_fields(tmp_path: Path) -> None:
    source = _make_manager(tmp_path)
    source.set(
        "widgets",
        {
            "steam": {
                "api_key": SENTINEL_KEY,
                "profile_identifier": SENTINEL_PROFILE,
                "safe_card_setting": True,
            }
        },
    )
    export_path = tmp_path / "steam_settings.sst"

    assert source.export_to_sst(str(export_path)) is True

    exported = export_path.read_text(encoding="utf-8")
    assert SENTINEL_KEY not in exported
    assert SENTINEL_PROFILE not in exported
    assert "safe_card_setting" in exported

    target = _make_manager(tmp_path)
    malicious_payload = {
        "snapshot": {
            "widgets": {
                "steam": {
                    "api_key": SENTINEL_KEY,
                    "profile_identifier": SENTINEL_PROFILE,
                    "safe_card_setting": True,
                }
            }
        }
    }
    malicious_path = tmp_path / "malicious_steam_settings.sst"
    malicious_path.write_text(json.dumps(malicious_payload), encoding="utf-8")

    assert target.import_from_sst(str(malicious_path), merge=True) is True

    steam_settings = target.get("widgets")["steam"]
    assert steam_settings == {"safe_card_setting": True}


def test_disconnect_account_clears_credentials_and_account_private_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from core.settings import storage_paths

    storage_paths.reset_module_cache()
    credential = SteamCredentialPayload(
        api_key=SENTINEL_KEY,
        profile_identifier=SENTINEL_PROFILE,
    )
    save_credentials(credential, encrypt_func=lambda payload: b"dpapi::opaque")
    cache_dir = get_profile_cache_dir_for_credentials(credential)
    (cache_dir / "catalog-v1.json").write_text("{}", encoding="utf-8")

    assert cache_dir.exists()
    assert get_storage_status().has_credentials is True

    disconnect_account()

    assert get_storage_status().has_credentials is False
    assert not any((tmp_path / "SRPSS" / "steam" / "cache").iterdir())


def test_steam_credential_input_status_is_ui_safe(monkeypatch) -> None:
    monkeypatch.setattr("core.steam.credentials.steam_storage_available", lambda: True)

    missing_key = validate_credential_input("", SENTINEL_PROFILE)
    missing_profile = validate_credential_input(SENTINEL_KEY, "")
    ready = validate_credential_input(SENTINEL_KEY, SENTINEL_PROFILE)

    assert missing_key.can_test is False
    assert missing_profile.can_test is False
    assert ready.can_test is True
    assert ready.can_save_after_test is False
    assert SENTINEL_KEY not in ready.message
    assert SENTINEL_PROFILE not in ready.message
