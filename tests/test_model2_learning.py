from decimal import Decimal

import pytest

from app.model2_learning import aggregate_source_metrics


def test_aggregate_source_metrics_sums_complete_metrics_with_decimal_precision():
    result = aggregate_source_metrics(
        [
            {
                "impression": 10,
                "save": 2.25,
                "pin_click": 1,
                "outbound_click": 0.5,
            },
            {
                "impression": 5,
                "save": 3.75,
                "pin_click": 2,
                "outbound_click": 1.5,
            },
        ]
    )

    assert result == {
        "impression": 15,
        "save": 6,
        "pin_click": 3,
        "outbound_click": 2,
    }


def test_aggregate_source_metrics_keeps_only_incomplete_metrics_unknown():
    result = aggregate_source_metrics(
        [
            {"impression": 10, "save": 2, "pin_click": None, "outbound_click": 1},
            {"impression": 5, "save": None, "pin_click": 3, "outbound_click": 2},
        ]
    )

    assert result == {
        "impression": 15,
        "save": None,
        "pin_click": None,
        "outbound_click": 3,
    }


def test_aggregate_source_metrics_preserves_fractional_decimal_values():
    result = aggregate_source_metrics(
        [
            {"impression": Decimal("0.1"), "save": 0, "pin_click": 0, "outbound_click": 0},
            {"impression": Decimal("0.2"), "save": 0, "pin_click": 0, "outbound_click": 0},
        ]
    )
    assert result["impression"] == pytest.approx(0.3)


def test_aggregate_source_metrics_empty_input_is_all_unknown():
    assert aggregate_source_metrics([]) == {
        "impression": None,
        "save": None,
        "pin_click": None,
        "outbound_click": None,
    }


@pytest.mark.parametrize(
    "source",
    [
        {"impression": 1, "unsupported_metric": 2},
        {"impression": "10"},
        {"impression": True},
        {"impression": -1},
        {"impression": float("nan")},
        {"impression": float("inf")},
    ],
)
def test_aggregate_source_metrics_rejects_invalid_or_unsupported_values(source):
    with pytest.raises(ValueError):
        aggregate_source_metrics([source])
