"""Global API credential storage keyed by site preset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from urllib.parse import parse_qs, urlparse

import yaml

from danbooru_download.core.danbooru_client import (
    PROFILE_DANBOORU,
    PROFILE_GELBOORU,
    PROFILE_MOEBOORU,
    PROFILE_NOZOMI,
    _detect_profile,
)
from danbooru_download.core.config import Config


SITE_PRESET_URLS = {
    "Danbooru": "https://danbooru.donmai.us",
    "AIBooru": "https://aibooru.online",
    "Gelbooru": "https://gelbooru.com",
    "Safebooru": "https://safebooru.donmai.us",
    "Yande.re": "https://yande.re",
    "Nozomi.la": "https://nozomi.la",
}

PRESET_PROFILES = {
    "Danbooru": PROFILE_DANBOORU,
    "AIBooru": PROFILE_DANBOORU,
    "Gelbooru": PROFILE_GELBOORU,
    "Safebooru": PROFILE_DANBOORU,
    "Yande.re": PROFILE_MOEBOORU,
    "Nozomi.la": PROFILE_NOZOMI,
}

AUTH_HELP_URLS = {
    PROFILE_GELBOORU: "https://gelbooru.com/index.php?page=account&s=options",
    PROFILE_DANBOORU: "https://danbooru.donmai.us/profile",
    PROFILE_MOEBOORU: "https://yande.re/user/login",
}


@dataclass(frozen=True)
class AuthProfile:
    profile: str
    username_label: str
    auth_required: bool
    help_url: str


@dataclass
class SiteCredential:
    username: Optional[str] = None
    api_key: Optional[str] = None


def preset_for_url(base_url: str) -> str:
    """Return the site preset label for a base URL."""
    normalized = (base_url or "").rstrip("/")
    for label, preset_url in SITE_PRESET_URLS.items():
        if normalized == preset_url.rstrip("/"):
            return label

    profile = _detect_profile(base_url)
    for label, mapped_profile in PRESET_PROFILES.items():
        if mapped_profile == profile:
            return label
    return "Danbooru"


def get_auth_profile(base_url: str) -> AuthProfile:
    """Return auth metadata for a site URL."""
    profile = _detect_profile(base_url)
    if profile == PROFILE_GELBOORU:
        return AuthProfile(
            profile=profile,
            username_label="user_id",
            auth_required=True,
            help_url=AUTH_HELP_URLS[PROFILE_GELBOORU],
        )
    if profile == PROFILE_DANBOORU:
        return AuthProfile(
            profile=profile,
            username_label="username",
            auth_required=False,
            help_url=AUTH_HELP_URLS[PROFILE_DANBOORU],
        )
    return AuthProfile(
        profile=profile,
        username_label="username",
        auth_required=False,
        help_url=AUTH_HELP_URLS.get(profile, AUTH_HELP_URLS[PROFILE_DANBOORU]),
    )


def validate_credentials(
    base_url: str,
    username: Optional[str],
    api_key: Optional[str],
) -> list[str]:
    """Return validation error messages for credential input."""
    errors: list[str] = []
    auth = get_auth_profile(base_url)
    user = (username or "").strip()
    key = (api_key or "").strip()

    if auth.auth_required and (not user or not key):
        errors.append("auth_required")
        return errors

    if auth.profile == PROFILE_GELBOORU and user and not user.isdigit():
        errors.append("auth_validation_user_id")

    return errors


def _first_query_value(values) -> Optional[str]:
    if not values:
        return None
    value = str(values[0]).strip()
    return value or None


def parse_credential_blob(text: str) -> tuple[Optional[str], Optional[str]]:
    """Parse Gelbooru-style query strings and common credential variants."""
    raw = (text or "").strip()
    if not raw:
        return None, None

    lowered = raw.lower()
    if not any(
        key in lowered
        for key in ("api_key=", "user_id=", "username=", "login=")
    ):
        return None, None

    query = raw
    if "?" in raw:
        query = urlparse(raw).query
    else:
        query = raw.lstrip("&")

    if not query:
        return None, None

    params = parse_qs(query, keep_blank_values=False)
    params_lower = {str(key).lower(): value for key, value in params.items()}

    api_key = _first_query_value(params_lower.get("api_key"))
    user_id = _first_query_value(params_lower.get("user_id"))
    username = _first_query_value(params_lower.get("username")) or _first_query_value(
        params_lower.get("login")
    )
    identity = user_id or username
    if api_key and identity:
        return identity, api_key
    return None, None


class CredentialsStore:
    """Load and save API credentials per site preset."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._credentials: dict[str, SiteCredential] = {}

    def load(self) -> None:
        if not self.path.exists():
            self._credentials = {}
            return

        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw = data.get("credentials", {})
        self._credentials = {}
        if not isinstance(raw, dict):
            return

        for preset, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            self._credentials[str(preset)] = SiteCredential(
                username=str(payload.get("username") or "").strip() or None,
                api_key=str(payload.get("api_key") or "").strip() or None,
            )

    def save(self) -> None:
        payload = {
            "credentials": {
                preset: {
                    "username": cred.username or "",
                    "api_key": cred.api_key or "",
                }
                for preset, cred in self._credentials.items()
                if cred.username or cred.api_key
            }
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(payload, f, default_flow_style=False, allow_unicode=True)

    def get_for_preset(self, preset: str) -> SiteCredential:
        return self._credentials.get(preset, SiteCredential())

    def get_for_url(self, base_url: str) -> SiteCredential:
        return self.get_for_preset(preset_for_url(base_url))

    def set_for_preset(
        self,
        preset: str,
        username: Optional[str],
        api_key: Optional[str],
    ) -> None:
        self._credentials[preset] = SiteCredential(
            username=(username or "").strip() or None,
            api_key=(api_key or "").strip() or None,
        )

    def apply_to_config(
        self,
        config: Config,
        *,
        override_username: Optional[str] = None,
        override_api_key: Optional[str] = None,
    ) -> Config:
        """Fill missing config credentials from the global store."""
        if override_username:
            config.username = override_username
        if override_api_key:
            config.api_key = override_api_key

        if config.username and config.api_key:
            return config

        cred = self.get_for_url(config.base_url)
        if not config.username and cred.username:
            config.username = cred.username
        if not config.api_key and cred.api_key:
            config.api_key = cred.api_key
        return config

    def migrate_from_config(self, config: Config, preset: str) -> bool:
        """Move credentials from a task config into the global store if empty."""
        changed = False
        existing = self.get_for_preset(preset)
        username = (config.username or "").strip() or None
        api_key = (config.api_key or "").strip() or None

        if username and not existing.username:
            existing.username = username
            changed = True
        if api_key and not existing.api_key:
            existing.api_key = api_key
            changed = True

        if changed:
            self._credentials[preset] = existing
        return changed


def default_credentials_path(app_dir: Path) -> Path:
    return app_dir / "api_credentials.yaml"
