import pytest

import app


@pytest.mark.parametrize(
    "value,expected",
    [
        (123.456, "CHF 123.46"),
        (1234.0, "CHF 1'234"),
        (1_500_000, "CHF 1.50M"),
        (None, "—"),
    ],
)
def test_fmt_chf_formats_currency(value, expected):
    assert app.fmt_chf(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (999, "999.0"),
        (12_345, "12'345.0"),
        (2_500_000, "2.5M"),
        (None, "—"),
    ],
)
def test_fmt_num_formats_general_numbers(value, expected):
    assert app.fmt_num(value, dec=1) == expected


def test_score_badge_renders_expected_css_class():
    assert 'bdg-clean' in app.score_badge(0)
    assert 'bdg-alert' in app.score_badge(2)
    assert 'bdg-severe' in app.score_badge(5)
    assert 'bdg-extreme' in app.score_badge(7)

