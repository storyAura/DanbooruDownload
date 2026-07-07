import tempfile
import unittest
from pathlib import Path

from danbooru_download.core.config import Config
from danbooru_download.core.credentials import (
    CredentialsStore,
    get_auth_profile,
    parse_credential_blob,
    preset_for_url,
    validate_credentials,
)


class CredentialsStoreTests(unittest.TestCase):
    def test_round_trips_credentials_by_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_credentials.yaml"
            store = CredentialsStore(path)
            store.set_for_preset("Gelbooru", "1234567", "secret-key")
            store.save()
            store.load()
            cred = store.get_for_preset("Gelbooru")
            self.assertEqual(cred.username, "1234567")
            self.assertEqual(cred.api_key, "secret-key")

    def test_apply_to_config_uses_global_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_credentials.yaml"
            store = CredentialsStore(path)
            store.set_for_preset("Gelbooru", "42", "abc")
            store.save()
            store.load()

            config = Config(base_url="https://gelbooru.com")
            store.apply_to_config(config)
            self.assertEqual(config.username, "42")
            self.assertEqual(config.api_key, "abc")

    def test_migrate_from_config_only_when_store_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_credentials.yaml"
            store = CredentialsStore(path)
            config = Config(
                base_url="https://gelbooru.com",
                username="123",
                api_key="key",
            )
            changed = store.migrate_from_config(config, "Gelbooru")
            self.assertTrue(changed)
            cred = store.get_for_preset("Gelbooru")
            self.assertEqual(cred.username, "123")
            self.assertEqual(cred.api_key, "key")

            changed_again = store.migrate_from_config(config, "Gelbooru")
            self.assertFalse(changed_again)


class CredentialsValidationTests(unittest.TestCase):
    def test_gelbooru_requires_numeric_user_id(self):
        errors = validate_credentials(
            "https://gelbooru.com",
            "storyaura",
            "secret",
        )
        self.assertIn("auth_validation_user_id", errors)

    def test_preset_for_custom_gelbooru_url(self):
        self.assertEqual(preset_for_url("https://gelbooru.com"), "Gelbooru")

    def test_gelbooru_auth_profile_uses_user_id(self):
        auth = get_auth_profile("https://gelbooru.com")
        self.assertEqual(auth.username_label, "user_id")
        self.assertTrue(auth.auth_required)


class CredentialBlobParseTests(unittest.TestCase):
    def test_parses_gelbooru_query_string(self):
        username, api_key = parse_credential_blob(
            "&api_key=abc123&user_id=1882224"
        )
        self.assertEqual(username, "1882224")
        self.assertEqual(api_key, "abc123")

    def test_parses_reversed_query_order(self):
        username, api_key = parse_credential_blob(
            "user_id=42&api_key=secret"
        )
        self.assertEqual(username, "42")
        self.assertEqual(api_key, "secret")

    def test_parses_query_from_url(self):
        username, api_key = parse_credential_blob(
            "https://gelbooru.com/index.php?api_key=key9&user_id=1001"
        )
        self.assertEqual(username, "1001")
        self.assertEqual(api_key, "key9")

    def test_ignores_plain_text(self):
        self.assertEqual(parse_credential_blob("1882224"), (None, None))
        self.assertEqual(parse_credential_blob("storyaura"), (None, None))


if __name__ == "__main__":
    unittest.main()
