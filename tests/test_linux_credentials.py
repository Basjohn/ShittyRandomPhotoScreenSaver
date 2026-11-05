"""Linux credential protection: Secret Service keyring key + AES-GCM, never plaintext."""
from __future__ import annotations

import pytest

from core import secret_service_key
from core.windows import dpapi


def test_payloads_are_keyring_protected_and_round_trip(protected_storage, tmp_path) -> None:
    blob = dpapi.encrypt_user_data(b"super-secret-token")
    assert blob.startswith(dpapi.KEYRING_PREFIX) and dpapi.is_protected(blob)
    assert b"super-secret" not in blob
    assert dpapi.encrypt_user_data(b"super-secret-token") != blob  # fresh nonce per write
    assert dpapi.decrypt_user_data(blob) == b"super-secret-token"

    target = tmp_path / "creds.bin"
    dpapi.save_encrypted(target, b"app-password")
    assert b"app-password" not in target.read_bytes()
    assert dpapi.load_encrypted(target) == b"app-password"


def test_tampered_or_foreign_payloads_never_decrypt(protected_storage) -> None:
    from cryptography.exceptions import InvalidTag

    blob = bytearray(dpapi.encrypt_user_data(b"secret"))
    blob[-3] ^= 0x01
    with pytest.raises((InvalidTag, ValueError)):
        dpapi.decrypt_user_data(bytes(blob))
    with pytest.raises(ValueError):
        dpapi.decrypt_user_data(b"plain::secret")  # the retired fallback is not accepted


def test_without_a_keyring_nothing_is_persisted(monkeypatch, tmp_path) -> None:
    def no_keyring(*, create):
        raise secret_service_key.SecretServiceUnavailable("no Secret Service keyring is running in this session")

    monkeypatch.setattr(secret_service_key, "user_key", no_keyring)
    monkeypatch.setattr(secret_service_key, "available", lambda: False)
    target = tmp_path / "creds.bin"
    with pytest.raises(secret_service_key.SecretServiceUnavailable):
        dpapi.save_encrypted(target, b"app-password")
    assert not target.exists()
    assert dpapi.protected_storage_available() is False

    from core.steam.credentials import steam_storage_available, validate_credential_input

    assert steam_storage_available() is False
    assert "keyring" in validate_credential_input("a" * 32, "76561197960265728").message


class _Item:
    def __init__(self, secret: bytes):
        self.secret = secret

    def is_locked(self):
        return False

    def unlock(self):
        return False

    def get_secret(self):
        return self.secret


class _Collection:
    def __init__(self):
        self.items: list[tuple[dict, _Item]] = []

    def search_items(self, attributes):
        return [item for attrs, item in self.items if all(attrs.get(k) == v for k, v in attributes.items())]

    def create_item(self, label, attributes, secret, replace=False):
        self.items.append((dict(attributes), _Item(bytes(secret))))


def test_the_user_key_is_created_once_then_reused_and_must_exist_to_read(monkeypatch) -> None:
    collection = _Collection()
    monkeypatch.setattr(secret_service_key, "_collection", lambda: collection)
    secret_service_key.forget_cached_key()
    try:
        with pytest.raises(secret_service_key.SecretServiceUnavailable):
            secret_service_key.user_key(create=False)  # reading never invents a key
        key = secret_service_key.user_key(create=True)
        assert len(key) == secret_service_key.KEY_BYTES and len(collection.items) == 1
        secret_service_key.forget_cached_key()
        assert secret_service_key.user_key(create=True) == key and len(collection.items) == 1
        collection.items[0][1].secret = b"short"
        secret_service_key.forget_cached_key()
        with pytest.raises(secret_service_key.SecretServiceUnavailable):
            secret_service_key.user_key(create=False)
    finally:
        secret_service_key.forget_cached_key()
