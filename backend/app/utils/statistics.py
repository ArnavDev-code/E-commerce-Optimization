"""Statistical testing utilities for conversion rates and A/B experiments.

Ensures strict mathematical and statistical integrity:
- Conversion success counts and denominators must be integer values.
- Conversion counts cannot exceed sample sizes.
- Two-proportion z-test with two-sided p-value calculation.
- Checks sample sufficiency and warns if expected cell counts are too low.
- Clearly separates statistical significance from business importance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class TwoProportionZTestResult:
    """Result of a two-proportion z-test."""

    count1: int
    n1: int
    rate1_pct: float

    count2: int
    n2: int
    rate2_pct: float

    absolute_difference_pct: float
    relative_difference_pct: float

    pooled_proportion: float
    standard_error: float
    z_statistic: float
    p_value: float

    is_statistically_significant: bool  # at alpha = 0.05
    confidence_level: float = 0.95

    is_sample_sufficient: bool = True
    warning_message: Optional[str] = None


def calculate_two_proportion_z_test(
    count1: int,
    n1: int,
    count2: int,
    n2: int,
    alpha: float = 0.05,
    min_cell_count: int = 5,
) -> TwoProportionZTestResult:
    """Perform a two-proportion z-test comparing two conversion rates.
    
    Parameters
    ----------
    count1 : int
        Number of successes/conversions in group 1 (e.g., control).
    n1 : int
        Sample size (trials/views/sessions) for group 1.
    count2 : int
        Number of successes/conversions in group 2 (e.g., treatment or comparison).
    n2 : int
        Sample size for group 2.
    alpha : float
        Significance threshold (default 0.05 for 95% confidence).
    min_cell_count : int
        Minimum expected successes and failures required for normal approximation validity.

    Returns
    -------
    TwoProportionZTestResult
    """
    # 1. Enforce Integer Inputs
    if not isinstance(count1, (int, Decimal)) or not isinstance(count2, (int, Decimal)):
        raise TypeError("Success counts must be integer numbers.")
    if not isinstance(n1, (int, Decimal)) or not isinstance(n2, (int, Decimal)):
        raise TypeError("Sample sizes must be integer numbers.")

    count1 = int(round(float(count1)))
    n1 = int(round(float(n1)))
    count2 = int(round(float(count2)))
    n2 = int(round(float(n2)))

    # 2. Domain Validation
    if n1 <= 0 or n2 <= 0:
        return TwoProportionZTestResult(
            count1=count1,
            n1=n1,
            rate1_pct=0.0,
            count2=count2,
            n2=n2,
            rate2_pct=0.0,
            absolute_difference_pct=0.0,
            relative_difference_pct=0.0,
            pooled_proportion=0.0,
            standard_error=0.0,
            z_statistic=0.0,
            p_value=1.0,
            is_statistically_significant=False,
            is_sample_sufficient=False,
            warning_message="Sample size must be greater than zero.",
        )

    if count1 < 0 or count1 > n1:
        raise ValueError(f"Conversion count1 ({count1}) must be between 0 and n1 ({n1}).")
    if count2 < 0 or count2 > n2:
        raise ValueError(f"Conversion count2 ({count2}) must be between 0 and n2 ({n2}).")

    p1 = count1 / n1
    p2 = count2 / n2
    rate1_pct = round(p1 * 100.0, 4)
    rate2_pct = round(p2 * 100.0, 4)

    abs_diff = round(rate2_pct - rate1_pct, 4)
    rel_diff = round(((p2 - p1) / p1 * 100.0), 4) if p1 > 0 else 0.0

    # 3. Pooled Proportion and Normal Approximation Check
    total_conversions = count1 + count2
    total_sample = n1 + n2
    p_pool = total_conversions / total_sample

    warning = None
    is_sufficient = True

    # Check rule-of-thumb: n*p >= min_cell_count and n*(1-p) >= min_cell_count
    if (
        count1 < min_cell_count
        or (n1 - count1) < min_cell_count
        or count2 < min_cell_count
        or (n2 - count2) < min_cell_count
    ):
        is_sufficient = False
        warning = (
            f"Expected cell count is low (< {min_cell_count} conversions). "
            "Normal approximation may have reduced accuracy; collect more traffic."
        )

    # Edge cases: 0% or 100% conversion in both groups
    if p_pool == 0.0 or p_pool == 1.0 or p1 == p2:
        return TwoProportionZTestResult(
            count1=count1,
            n1=n1,
            rate1_pct=rate1_pct,
            count2=count2,
            n2=n2,
            rate2_pct=rate2_pct,
            absolute_difference_pct=abs_diff,
            relative_difference_pct=rel_diff,
            pooled_proportion=p_pool,
            standard_error=0.0,
            z_statistic=0.0,
            p_value=1.0,
            is_statistically_significant=False,
            is_sample_sufficient=is_sufficient,
            warning_message=warning,
        )

    # 4. Standard Error and Z-Score
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
    if se == 0.0:
        return TwoProportionZTestResult(
            count1=count1,
            n1=n1,
            rate1_pct=rate1_pct,
            count2=count2,
            n2=n2,
            rate2_pct=rate2_pct,
            absolute_difference_pct=abs_diff,
            relative_difference_pct=rel_diff,
            pooled_proportion=p_pool,
            standard_error=0.0,
            z_statistic=0.0,
            p_value=1.0,
            is_statistically_significant=False,
            is_sample_sufficient=is_sufficient,
            warning_message=warning,
        )

    z = (p2 - p1) / se

    # 5. Two-Sided p-value using the standard normal error function
    # Phi(z) = 0.5 * (1 + erf(z / sqrt(2)))
    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    p_val = max(0.0, min(1.0, p_val))  # bound between 0 and 1

    is_sig = p_val < alpha

    return TwoProportionZTestResult(
        count1=count1,
        n1=n1,
        rate1_pct=rate1_pct,
        count2=count2,
        n2=n2,
        rate2_pct=rate2_pct,
        absolute_difference_pct=abs_diff,
        relative_difference_pct=rel_diff,
        pooled_proportion=round(p_pool, 6),
        standard_error=round(se, 6),
        z_statistic=round(z, 4),
        p_value=round(p_val, 6),
        is_statistically_significant=is_sig,
        confidence_level=1.0 - alpha,
        is_sample_sufficient=is_sufficient,
        warning_message=warning,
    )
