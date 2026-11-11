"""Pure Model 2 domain contracts.

These value contracts validate input only. They do not access PostgreSQL,
Pinterest, the credential vault, or any external provider.
"""
from __future__ import annotations

import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ACCOUNT_ID_RE = re.compile(r"^pinterest:[^:\s]+$")
_NICHE_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

AccountProfileStatus = Literal["active", "paused"]
NicheStatus = Literal["active", "archived"]
AssignmentStatus = Literal["active", "paused"]
SupportedRegion = Literal["US", "GB+IE"]


class Model2Contract(BaseModel):
    """Base for closed, bounded domain input contracts."""

    model_config = ConfigDict(extra="forbid", strict=True)


class AccountId(Model2Contract):
    value: str = Field(min_length=10, max_length=200)

    @field_validator("value")
    @classmethod
    def canonical_pinterest_account_id(cls, value: str) -> str:
        if value != value.strip() or not _ACCOUNT_ID_RE.fullmatch(value):
            raise ValueError("account_id must use canonical pinterest:<user_id> format")
        return value


class NicheSlug(Model2Contract):
    value: str = Field(min_length=1, max_length=120)

    @field_validator("value")
    @classmethod
    def canonical_slug(cls, value: str) -> str:
        if not _NICHE_SLUG_RE.fullmatch(value):
            raise ValueError("slug must be lowercase ASCII kebab-case")
        return value


class AccountProfileInput(Model2Contract):
    account_id: str = Field(min_length=10, max_length=200)
    display_name: str = Field(default="", max_length=120)
    status: AccountProfileStatus = "active"
    timezone: str = Field(default="UTC", min_length=1, max_length=100)

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        return AccountId(value=value).value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 120:
            raise ValueError("display_name must be at most 120 characters")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_iana_timezone(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("timezone must not contain surrounding whitespace")
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("timezone must be a valid IANA timezone") from None
        return value


class NicheInput(Model2Contract):
    slug: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    default_region: SupportedRegion = "US"
    status: NicheStatus = "active"

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return NicheSlug(value=value).value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("description must be at most 2000 characters")
        return value


class AccountNicheAssignmentInput(Model2Contract):
    account_id: str = Field(min_length=10, max_length=200)
    niche_id: int = Field(gt=0, strict=True)
    is_primary: bool = False
    status: AssignmentStatus = "active"
    settings: dict[str, object] = Field(default_factory=dict)

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        return AccountId(value=value).value

    @field_validator("settings")
    @classmethod
    def enforce_current_settings_contract(cls, value: dict[str, object]) -> dict[str, object]:
        # Migration 013 intentionally accepts only an empty object until a
        # concrete, versioned account-niche settings contract is approved.
        if value:
            raise ValueError("settings must be empty until a versioned contract is approved")
        return value
