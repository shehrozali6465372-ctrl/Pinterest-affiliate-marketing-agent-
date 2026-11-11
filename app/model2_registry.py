"""Protected Model 2 registry API; no Pinterest/provider side effects."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, ValidationError

from app.auth import require_api_key
from app.database import DatabaseConfigurationError
from app.model2_domain import (
    AccountId,
    AccountNicheAssignmentInput,
    AccountProfileInput,
    NicheInput,
)
from app.model2_repository import (
    Model2ConflictError,
    Model2NotFoundError,
    Model2RepositoryError,
    create_niche,
    get_account_profile,
    get_niche,
    list_account_niche_assignments,
    list_account_profiles,
    list_niches,
    save_account_niche_assignment,
    save_account_profile,
    update_niche,
)

router = APIRouter(
    prefix="/model2",
    tags=["model2-registry"],
    dependencies=[Depends(require_api_key)],
)


class RegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountProfileResponse(RegistryResponse):
    account_id: str
    display_name: str
    status: Literal["active", "paused"]
    timezone: str
    created_at: datetime
    updated_at: datetime


class NicheResponse(RegistryResponse):
    id: int
    slug: str
    display_name: str
    description: str
    default_region: Literal["US", "GB+IE"]
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime


class AccountNicheAssignmentResponse(RegistryResponse):
    account_id: str
    niche_id: int
    is_primary: bool
    status: Literal["active", "paused"]
    settings: dict[str, object]
    created_at: datetime
    updated_at: datetime


def _call_repository(operation, *args, **kwargs):
    """Translate known repository/storage failures without leaking SQL details."""
    try:
        return operation(*args, **kwargs)
    except Model2NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except Model2ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Model2RepositoryError:
        raise HTTPException(status_code=503, detail="Model 2 registry operation is temporarily unavailable.") from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Model 2 registry storage is temporarily unavailable.") from None


def _account_id(value: str) -> str:
    try:
        return AccountId(value=value).value
    except ValidationError:
        raise HTTPException(status_code=422, detail="account_id must use canonical pinterest:<user_id> format.") from None


def _require_explicit_fields(payload: BaseModel, *field_names: str) -> None:
    missing = [name for name in field_names if name not in payload.model_fields_set]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"These fields must be explicitly supplied: {', '.join(missing)}.",
        )


@router.get("/accounts", response_model=list[AccountProfileResponse])
def get_accounts() -> list[dict]:
    """List non-secret account profiles for the single authenticated operator."""
    return _call_repository(list_account_profiles)


@router.get("/accounts/{account_id}", response_model=AccountProfileResponse)
def get_account(account_id: str) -> dict:
    account_id = _account_id(account_id)
    row = _call_repository(get_account_profile, account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Account profile does not exist.")
    return row


@router.put("/accounts/{account_id}", response_model=AccountProfileResponse)
def put_account(account_id: str, payload: AccountProfileInput) -> dict:
    account_id = _account_id(account_id)
    if payload.account_id != account_id:
        raise HTTPException(status_code=422, detail="Path account_id must match payload account_id.")
    # PUT is a full state replacement: prevent omitted defaults from silently
    # reactivating an account or resetting its timezone.
    _require_explicit_fields(payload, "status", "timezone")
    return _call_repository(save_account_profile, payload)


@router.get(
    "/accounts/{account_id}/niches",
    response_model=list[AccountNicheAssignmentResponse],
)
def get_account_niches(account_id: str) -> list[dict]:
    account_id = _account_id(account_id)
    profile = _call_repository(get_account_profile, account_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Account profile does not exist.")
    return _call_repository(list_account_niche_assignments, account_id)


@router.put(
    "/accounts/{account_id}/niches/{niche_id}",
    response_model=AccountNicheAssignmentResponse,
)
def put_account_niche(
    account_id: str,
    niche_id: int = Path(gt=0),
    payload: AccountNicheAssignmentInput = ...,
) -> dict:
    account_id = _account_id(account_id)
    if payload.account_id != account_id or payload.niche_id != niche_id:
        raise HTTPException(
            status_code=422,
            detail="Path account_id and niche_id must match the payload identifiers.",
        )
    _require_explicit_fields(payload, "status", "is_primary")
    return _call_repository(save_account_niche_assignment, payload)


@router.get("/niches", response_model=list[NicheResponse])
def get_niches(
    include_archived: bool = Query(default=False),
) -> list[dict]:
    return _call_repository(list_niches, include_archived=include_archived)


@router.post("/niches", status_code=201, response_model=NicheResponse)
def post_niche(payload: NicheInput) -> dict:
    return _call_repository(create_niche, payload)


@router.get("/niches/{niche_id}", response_model=NicheResponse)
def get_niche_by_id(niche_id: int = Path(gt=0)) -> dict:
    row = _call_repository(get_niche, niche_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Niche does not exist.")
    return row


@router.put("/niches/{niche_id}", response_model=NicheResponse)
def put_niche(niche_id: int = Path(gt=0), payload: NicheInput = ...) -> dict:
    # Require explicit lifecycle and region values; omitting status must not
    # accidentally reactivate an archived niche.
    _require_explicit_fields(payload, "status", "default_region")
    return _call_repository(update_niche, niche_id, payload)
