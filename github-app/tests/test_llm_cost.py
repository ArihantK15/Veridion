import pytest

from app_server.llm_cost import cost_for_usage, monthly_cap_for_installation


def test_cost_for_usage_deepseek_v4_pro():
    assert cost_for_usage("deepseek-v4-pro", 1_000_000, 1_000_000) == pytest.approx(
        0.435 + 0.87
    )


def test_cost_for_usage_deepseek_v4_flash():
    assert cost_for_usage("deepseek-v4-flash", 1_000_000, 1_000_000) == pytest.approx(
        0.14 + 0.28
    )


def test_cost_for_usage_small_real_call():
    expected = (2_000 * 0.14 + 300 * 0.28) / 1_000_000
    assert cost_for_usage("deepseek-v4-flash", 2_000, 300) == pytest.approx(expected)


def test_monthly_cap_for_installation_base_only():
    assert monthly_cap_for_installation(7.00, 0) == pytest.approx(7.00)


def test_monthly_cap_for_installation_with_extra_seats():
    assert monthly_cap_for_installation(7.00, 3) == pytest.approx(13.00)
