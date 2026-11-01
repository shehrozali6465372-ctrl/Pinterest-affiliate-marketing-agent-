"""Single source of truth for Pinterest Pin text constraints."""

PIN_TITLE_MAX_LENGTH = 100
PIN_DESCRIPTION_MAX_LENGTH = 800
PIN_ALT_TEXT_MAX_LENGTH = 500


def validate_pin_text_fields(*, title: object, description: object, alt_text: object) -> None:
    """Fail closed before sending Pin text that exceeds Pinterest API limits."""
    limits = (
        ("title", title, PIN_TITLE_MAX_LENGTH),
        ("description", description, PIN_DESCRIPTION_MAX_LENGTH),
        ("alt_text", alt_text, PIN_ALT_TEXT_MAX_LENGTH),
    )
    for field_name, value, maximum in limits:
        if not isinstance(value, str):
            raise ValueError(f"Pinterest Pin {field_name} must be a string.")
        if len(value) > maximum:
            raise ValueError(
                f"Pinterest Pin {field_name} exceeds the {maximum}-character API limit."
            )
