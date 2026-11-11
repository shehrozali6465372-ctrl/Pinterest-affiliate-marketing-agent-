import pytest
from pydantic import ValidationError

from app.model2_domain import (
    AccountId,
    AccountNicheAssignmentInput,
    AccountProfileInput,
    NicheInput,
    NicheSlug,
)


def test_account_id_accepts_canonical_pinterest_identity():
    assert AccountId(value="pinterest:123456789").value == "pinterest:123456789"


@pytest.mark.parametrize("value", [
    "123456789",
    "pinterest:",
    "pinterest:has space",
    "pinterest:two:segments",
    " pinterest:123",
    "pinterest:123 ",
])
def test_account_id_rejects_noncanonical_values(value):
    with pytest.raises(ValidationError):
        AccountId(value=value)


def test_niche_slug_accepts_lowercase_kebab_case():
    assert NicheSlug(value="home-decor-kitchen").value == "home-decor-kitchen"


@pytest.mark.parametrize("value", [
    "Home-Decor",
    "home_decor",
    "-home",
    "home-",
    "home--decor",
    "home decor",
    "café",
])
def test_niche_slug_rejects_noncanonical_values(value):
    with pytest.raises(ValidationError):
        NicheSlug(value=value)


def test_account_profile_normalizes_display_name_and_validates_iana_timezone():
    profile = AccountProfileInput(
        account_id="pinterest:123456789",
        display_name="  Kitchen Account  ",
        timezone="Asia/Karachi",
    )
    assert profile.display_name == "Kitchen Account"
    assert profile.timezone == "Asia/Karachi"


def test_account_profile_rejects_unknown_timezone():
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        AccountProfileInput(account_id="pinterest:123456789", timezone="Mars/Olympus")


def test_niche_contract_reuses_supported_regions_and_normalizes_text():
    niche = NicheInput(
        slug="home-decor",
        display_name="  Home Decor  ",
        description="  Room styling  ",
        default_region="GB+IE",
    )
    assert niche.display_name == "Home Decor"
    assert niche.description == "Room styling"
    assert niche.default_region == "GB+IE"


def test_niche_contract_rejects_unsupported_region():
    with pytest.raises(ValidationError):
        NicheInput(slug="home-decor", display_name="Home Decor", default_region="CA")


def test_paused_assignment_may_retain_primary_flag_without_being_active_primary():
    assignment = AccountNicheAssignmentInput(
        account_id="pinterest:123456789",
        niche_id=1,
        is_primary=True,
        status="paused",
    )
    assert assignment.is_primary is True
    assert assignment.status == "paused"


def test_assignment_keeps_settings_closed_until_contract_is_approved():
    with pytest.raises(ValidationError, match="settings must be empty"):
        AccountNicheAssignmentInput(
            account_id="pinterest:123456789",
            niche_id=1,
            settings={"market": "US"},
        )


def test_assignment_accepts_nonprimary_active_mapping():
    assignment = AccountNicheAssignmentInput(
        account_id="pinterest:123456789",
        niche_id=1,
    )
    assert assignment.status == "active"
    assert assignment.is_primary is False
    assert assignment.settings == {}


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        AccountProfileInput(account_id="pinterest:123456789", owner_id="operator")


def test_account_id_enforces_database_length_bounds():
    assert AccountId(value="pinterest:" + "a" * 190).value.endswith("a" * 190)
    with pytest.raises(ValidationError):
        AccountId(value="pinterest:" + "a" * 191)


def test_account_id_allows_unicode_user_id_when_canonical_shape_is_preserved():
    assert AccountId(value="pinterest:用户123").value == "pinterest:用户123"


def test_niche_slug_enforces_application_length_bound():
    assert NicheSlug(value="a" * 120).value == "a" * 120
    with pytest.raises(ValidationError):
        NicheSlug(value="a" * 121)


def test_niche_display_name_must_not_be_blank_after_normalization():
    with pytest.raises(ValidationError, match="must not be blank"):
        NicheInput(slug="home-decor", display_name="   ")


def test_niche_description_respects_database_length_bound():
    with pytest.raises(ValidationError):
        NicheInput(slug="home-decor", display_name="Home Decor", description="x" * 2001)


def test_timezone_rejects_surrounding_whitespace_and_invalid_values():
    with pytest.raises(ValidationError, match="surrounding whitespace"):
        AccountProfileInput(account_id="pinterest:123456789", timezone=" UTC ")


def test_assignment_niche_id_is_positive_strict_integer():
    with pytest.raises(ValidationError):
        AccountNicheAssignmentInput(account_id="pinterest:123456789", niche_id="1")
    with pytest.raises(ValidationError):
        AccountNicheAssignmentInput(account_id="pinterest:123456789", niche_id=True)
    with pytest.raises(ValidationError):
        AccountNicheAssignmentInput(account_id="pinterest:123456789", niche_id=0)


def test_contracts_do_not_coerce_wrong_scalar_types():
    with pytest.raises(ValidationError):
        AccountProfileInput(account_id="pinterest:123456789", display_name=123)
    with pytest.raises(ValidationError):
        AccountNicheAssignmentInput(account_id="pinterest:123456789", niche_id=1, is_primary="true")
