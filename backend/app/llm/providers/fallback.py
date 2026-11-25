"""Deterministic rule-based fallback provider for diagnosis and recommendations.

Requires no external API keys, zero network connectivity, and guarantees
reproducible, mathematically grounded, and schema-compliant outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List
from app.llm.base import (
    BaseLLMProvider,
    ConfirmedObservation,
    DiagnosisOutput,
    HypothesisExplanation,
    RecommendationItem,
)


class FallbackLLMProvider(BaseLLMProvider):
    """Deterministic fallback provider executing vetted CRO logic."""

    @property
    def provider_name(self) -> str:
        return "fallback"

    def is_available(self) -> bool:
        return True

    def diagnose_leak(self, context: Dict[str, Any]) -> DiagnosisOutput:
        leak_type = context.get("leak_type", "")
        product_name = context.get("product_title", "Product")
        observed = str(context.get("observed_value", "0"))
        baseline = str(context.get("baseline_value", "0"))
        sample = int(context.get("sample_size", 0))
        p_val = context.get("p_value")
        is_sig = context.get("is_significant", False)
        metric_name = context.get("metric_affected", "conversion_rate")
        price = context.get("price")
        unit_cost = context.get("unit_cost")
        stock = context.get("inventory_quantity")

        if leak_type == "low_atc_rate":
            return DiagnosisOutput(
                issue_summary=(
                    f"'{product_name}' generates substantial traffic ({sample:,} views) but has an "
                    f"Add-to-Cart rate of {observed}%, significantly below the catalog benchmark of {baseline}%."
                ),
                observations=[
                    ConfirmedObservation(
                        metric="Add-to-Cart Rate",
                        observed_value=f"{observed}%",
                        baseline_value=f"{baseline}%",
                        sample_size=sample,
                        context=f"Tested against catalog median across {sample:,} product views."
                        + (" Statistically significant (p < 0.05)." if is_sig else " Directional evidence."),
                    ),
                    ConfirmedObservation(
                        metric="Pricing & Economics",
                        observed_value=f"${price:.2f}" if price is not None else "Unknown",
                        baseline_value="Catalog Median",
                        sample_size=sample,
                        context=(
                            f"Gross margin: {context.get('margin_pct', 'N/A')}%"
                            if context.get('margin_pct') is not None
                            else "COGS not provided."
                        ),
                    ),
                ],
                hypotheses=[
                    HypothesisExplanation(
                        hypothesis="Above-the-fold imagery and copy do not immediately convey unique value or product fit.",
                        supporting_signals=[
                            f"High page traffic ({sample:,} views) with only {observed}% conversion to cart",
                            "Visitors exit without engaging with the product options or size selectors",
                        ],
                        likelihood="high",
                    ),
                    HypothesisExplanation(
                        hypothesis="Shipping cost or return policy uncertainty before cart creation causes purchase hesitation.",
                        supporting_signals=[
                            "Lack of explicit free shipping thresholds visible beside the Buy button",
                            "Price sensitivity at current price point without immediate trust badges",
                        ],
                        likelihood="medium",
                    ),
                    HypothesisExplanation(
                        hypothesis="Missing or low-visibility customer social proof (reviews, ratings, UGC) at point of decision.",
                        supporting_signals=[
                            "No star rating visible immediately beneath the product title",
                        ],
                        likelihood="medium",
                    ),
                ],
                missing_information=[
                    "Mobile scroll depth distribution (percentage of visitors who reach the Add-to-Cart button).",
                    "Traffic source breakdown (paid social vs. organic search conversion delta).",
                    "Page load speed and Largest Contentful Paint (LCP) across mobile devices.",
                ],
                recommended_investigation=[
                    "Inspect session recordings or scroll-map data to confirm whether mobile visitors view the Buy Box.",
                    "Segment ATC rate by traffic source in GA4 to check if low conversion is confined to paid ads.",
                    "Verify that all product variants and size options display clear availability without confusion.",
                ],
                recommended_actions=[
                    "Implement a persistent sticky Add-to-Cart bar for mobile viewports.",
                    "Prominently place verified customer review stars and photo snippets directly beside product price.",
                    "Add transparent shipping and return badges (e.g., 'Free 3-day shipping & 30-day returns') above the fold.",
                ],
                confidence_level="high" if is_sig and sample >= 100 else "medium",
            )

        elif leak_type == "atc_rate_decline":
            return DiagnosisOutput(
                issue_summary=(
                    f"'{product_name}' experienced an abrupt decline in Add-to-Cart rate from {baseline}% "
                    f"down to {observed}% over recent comparison periods."
                ),
                observations=[
                    ConfirmedObservation(
                        metric="Add-to-Cart Rate Delta",
                        observed_value=f"{observed}%",
                        baseline_value=f"{baseline}%",
                        sample_size=sample,
                        context=f"Comparison vs prior equivalent period across {sample:,} recent visits."
                        + (" Statistically significant drop (p < 0.05)." if is_sig else " Potential emerging trend."),
                    ),
                    ConfirmedObservation(
                        metric="Inventory Status",
                        observed_value=f"{stock} units" if stock is not None else "Unknown",
                        baseline_value="In Stock (>20)",
                        sample_size=1,
                        context="Checked across active product variants.",
                    ),
                ],
                hypotheses=[
                    HypothesisExplanation(
                        hypothesis="Key popular sizes or variants went out of stock, frustrating potential buyers.",
                        supporting_signals=[
                            f"Current inventory level is {stock} units" if stock is not None else "Stock levels unconfirmed",
                            "Sudden period-over-period conversion contraction",
                        ],
                        likelihood="high" if stock is not None and stock < 20 else "medium",
                    ),
                    HypothesisExplanation(
                        hypothesis="Recent store theme, JavaScript app, or layout update introduced a rendering bug on mobile.",
                        supporting_signals=[
                            "Rapid drop without corresponding reduction in raw traffic volume",
                        ],
                        likelihood="medium",
                    ),
                    HypothesisExplanation(
                        hypothesis="Shift in marketing campaign audience mix brought lower-intent traffic to this landing page.",
                        supporting_signals=[
                            "Traffic volume held steady while conversion dropped sharply",
                        ],
                        likelihood="medium",
                    ),
                ],
                missing_information=[
                    "Theme and Shopify app change log around the date of the conversion drop.",
                    "Variant-level historical stockout log during the comparison window.",
                    "Client-side JavaScript error logs from storefront visitors.",
                ],
                recommended_investigation=[
                    "Cross-reference the drop date with Shopify theme publishes and app installations.",
                    "Check if core product variants (e.g. sizes M/L) were marked Out of Stock.",
                    "Perform test checkout on both iOS Safari and Android Chrome to test button responsiveness.",
                ],
                recommended_actions=[
                    "Enable 'Back in Stock' email notifications on sold-out variants with estimated restock dates.",
                    "Run automated storefront script checks to verify Add-to-Cart AJAX triggers fire without console errors.",
                    "Temporarily pause lower-converting top-of-funnel ad adsets pointing directly to this product.",
                ],
                confidence_level="high" if is_sig else "medium",
            )

        elif leak_type == "high_atc_low_checkout":
            return DiagnosisOutput(
                issue_summary=(
                    f"Shoppers show strong intent by adding '{product_name}' to cart ({sample:,} additions), "
                    f"but only {observed}% proceed to checkout (store benchmark is {baseline}%)."
                ),
                observations=[
                    ConfirmedObservation(
                        metric="Cart-to-Checkout Progression",
                        observed_value=f"{observed}%",
                        baseline_value=f"{baseline}%",
                        sample_size=sample,
                        context=f"Only {observed}% of {sample:,} cart additions transitioned to checkout initiation.",
                    ),
                ],
                hypotheses=[
                    HypothesisExplanation(
                        hypothesis="Unexpected shipping rates or delivery timelines first revealed inside the cart drawer trigger sticker shock.",
                        supporting_signals=[
                            f"{float(observed):.1f}% checkout progression indicates dropoff occurs before reaching Shopify checkout",
                            "Customers use cart as a price-checking tool before abandoning",
                        ],
                        likelihood="high",
                    ),
                    HypothesisExplanation(
                        hypothesis="Cart drawer lacks a distinct, high-contrast Checkout button or is hindered by aggressive upsell popups.",
                        supporting_signals=[
                            "Visitors add item to cart but abandon within the cart drawer interface",
                        ],
                        likelihood="medium",
                    ),
                    HypothesisExplanation(
                        hypothesis="Missing dynamic payment options (Shop Pay, Apple Pay) in the cart drawer forces unnecessary friction.",
                        supporting_signals=[
                            "Customers desiring rapid 1-tap checkout bounce when required to enter full address details",
                        ],
                        likelihood="medium",
                    ),
                ],
                missing_information=[
                    "Cart drawer vs /cart full page view distribution.",
                    "Shipping estimator usage rate inside the shopping cart.",
                    "Coupon code input error rate in the cart interface.",
                ],
                recommended_investigation=[
                    "Verify how shipping rates and thresholds are communicated in the cart drawer.",
                    "Audit cart drawer load performance and ensure CTA is fixed and visible above mobile keyboard.",
                    "Inspect whether discount code errors cause frustration in the cart.",
                ],
                recommended_actions=[
                    "Introduce a dynamic Free Shipping Progress Bar (e.g. 'Add $15 for Free Shipping') in the cart drawer.",
                    "Embed 1-click accelerated checkout buttons (Shop Pay, Apple Pay) directly inside the cart drawer.",
                    "Simplify cart drawer by removing distracting third-party cross-sells that obscure the primary Checkout CTA.",
                ],
                confidence_level="high" if sample >= 30 else "medium",
            )

        elif leak_type == "low_purchase_completion":
            return DiagnosisOutput(
                issue_summary=(
                    f"Checkout was initiated for '{product_name}' ({sample:,} times), but only {observed}% "
                    f"completed payment (store benchmark: {baseline}%)."
                ),
                observations=[
                    ConfirmedObservation(
                        metric="Checkout-to-Purchase Completion",
                        observed_value=f"{observed}%",
                        baseline_value=f"{baseline}%",
                        sample_size=sample,
                        context=f"Of {sample:,} initiated checkouts, only {observed}% resulted in a completed order.",
                    ),
                ],
                hypotheses=[
                    HypothesisExplanation(
                        hypothesis="High taxes, shipping costs, or unexpected delivery surcharges calculated at the final step cause payment abandonment.",
                        supporting_signals=[
                            "Drop-off occurs after customers have already entered personal contact information",
                        ],
                        likelihood="high",
                    ),
                    HypothesisExplanation(
                        hypothesis="Preferred localized payment methods (e.g., Shop Pay, Klarna, PayPal, Afterpay) are absent or failing.",
                        supporting_signals=[
                            "Shoppers abandon at the payment gateway selection stage",
                        ],
                        likelihood="high",
                    ),
                    HypothesisExplanation(
                        hypothesis="Security or trust concerns at payment screen (missing SSL/security badges or unclear return guarantees).",
                        supporting_signals=[
                            "New customer checkout completion rate lags repeat customer rate",
                        ],
                        likelihood="medium",
                    ),
                ],
                missing_information=[
                    "Shopify Checkout step dropoff breakdown (Customer Info vs Shipping Method vs Payment Method).",
                    "Payment gateway error and decline logs.",
                    "Zip code / regional shipping rate variance.",
                ],
                recommended_investigation=[
                    "Review Shopify Analytics > 'Checkout funnels' to isolate the exact checkout step where abandonments occur.",
                    "Check payment provider gateway dashboard for credit card decline codes or gateway latency.",
                    "Audit shipping zone configuration for unintentional expensive rate spikes.",
                ],
                recommended_actions=[
                    "Activate Shop Pay and express digital wallets to enable seamless 1-tap checkout completion.",
                    "Display money-back guarantees, secure 256-bit encryption badges, and clear return policy in checkout footer.",
                    "Offer flat-rate or free economy shipping options to eliminate price shock at final payment.",
                ],
                confidence_level="high" if sample >= 20 else "medium",
            )

        else:
            return DiagnosisOutput(
                issue_summary=f"Conversion dropoff identified for '{product_name}' on metric '{metric_name}'.",
                observations=[
                    ConfirmedObservation(
                        metric=metric_name,
                        observed_value=str(observed),
                        baseline_value=str(baseline),
                        sample_size=sample,
                        context="Deterministic leak detection.",
                    )
                ],
                hypotheses=[
                    HypothesisExplanation(
                        hypothesis="Funnel friction or messaging mismatch across buyer journey.",
                        supporting_signals=["Observed metric lags benchmark."],
                        likelihood="medium",
                    )
                ],
                missing_information=["Granular event telemetry and session recordings."],
                recommended_investigation=["Review customer journey logs and checkout telemetry."],
                recommended_actions=["Run controlled test modifying product messaging and call-to-action."],
                confidence_level="medium",
            )

    def generate_recommendations(self, context: Dict[str, Any]) -> List[RecommendationItem]:
        leak_type = context.get("leak_type", "")
        product_name = context.get("product_title", "Product")
        observed = str(context.get("observed_value", "0"))
        baseline = str(context.get("baseline_value", "0"))
        margin_pct = context.get("margin_pct")
        stock = context.get("inventory_quantity")

        items: List[RecommendationItem] = []

        if leak_type == "low_atc_rate":
            items.append(
                RecommendationItem(
                    title=f"Add Sticky Mobile Add-to-Cart & Trust Badges on {product_name}",
                    target_stage="product_page",
                    expected_direction="increase",
                    detected_problem=(
                        f"Add-to-cart rate is {observed}%, lagging store benchmark of {baseline}% on {product_name}."
                    ),
                    suggested_action=(
                        "Implement a persistent sticky Add-to-Cart bottom bar on mobile screens with visible "
                        "star ratings, stock reassurance, and primary variant selector."
                    ),
                    business_reason=(
                        "Reduces scroll fatigue and ensures the primary conversion action is always accessible, "
                        "typically lifting mobile product page conversions."
                    ),
                    implementation_effort="low",
                    confidence_level="high",
                    risks_or_prerequisites=[
                        "Ensure sticky bar does not obstruct chat widgets or accessibility cookies.",
                        "Check that variant dropdown works seamlessly on mobile viewports.",
                    ],
                    metric_to_monitor="add_to_cart_rate",
                )
            )
            items.append(
                RecommendationItem(
                    title=f"Enhance Product Gallery with Lifestyle Images & Video for {product_name}",
                    target_stage="product_page",
                    expected_direction="increase",
                    detected_problem=(
                        f"Visitors view {product_name} but hesitate to add it to cart ({observed}% vs {baseline}%)."
                    ),
                    suggested_action=(
                        "Add 2 lifestyle photos showing real-world product usage and a short 10-second silent video demo "
                        "in the first 3 media positions."
                    ),
                    business_reason=(
                        "Increases product comprehension, reduces perceived purchase risk, and boosts purchase intent."
                    ),
                    implementation_effort="medium",
                    confidence_level="medium",
                    risks_or_prerequisites=[
                        "High-resolution assets required.",
                        "Ensure media files are compressed to prevent page speed regressions.",
                    ],
                    metric_to_monitor="add_to_cart_rate",
                )
            )

        elif leak_type == "atc_rate_decline":
            items.append(
                RecommendationItem(
                    title=f"Audit Mobile Product Page Functionality & Restock {product_name}",
                    target_stage="product_page",
                    expected_direction="increase",
                    detected_problem=(
                        f"Add-to-cart rate declined from {baseline}% to {observed}% over recent periods."
                    ),
                    suggested_action=(
                        "Audit storefront scripts for JavaScript console errors, verify Add-to-Cart button responsiveness, "
                        "and configure restock alerts on any depleted variants."
                    ),
                    business_reason=(
                        "Recovers lost conversion rate caused by potential technical friction or variant stockouts."
                    ),
                    implementation_effort="low",
                    confidence_level="high",
                    risks_or_prerequisites=[
                        "Requires review of recent Shopify theme publish history.",
                    ],
                    metric_to_monitor="add_to_cart_rate",
                )
            )

        elif leak_type == "high_atc_low_checkout":
            items.append(
                RecommendationItem(
                    title=f"Add Free Shipping Progress Bar & Express Checkout to Cart Drawer",
                    target_stage="cart",
                    expected_direction="increase",
                    detected_problem=(
                        f"Cart abandonment is high: only {observed}% of shoppers adding {product_name} reach checkout."
                    ),
                    suggested_action=(
                        "Add a dynamic progress bar in the cart drawer showing how much more to add for free shipping, "
                        "plus Shop Pay / Apple Pay 1-click buttons."
                    ),
                    business_reason=(
                        "Addresses shipping cost apprehension before checkout and reduces checkout progression friction."
                    ),
                    implementation_effort="medium",
                    confidence_level="high",
                    risks_or_prerequisites=[
                        "Store shipping threshold settings must be clearly calibrated.",
                    ],
                    metric_to_monitor="checkout_rate",
                )
            )

        elif leak_type == "low_purchase_completion":
            items.append(
                RecommendationItem(
                    title=f"Enable 1-Click Shop Pay & Display Checkout Security Guarantees",
                    target_stage="checkout",
                    expected_direction="increase",
                    detected_problem=(
                        f"Only {observed}% of initiated checkouts complete purchase for {product_name}."
                    ),
                    suggested_action=(
                        "Ensure Shop Pay, Apple Pay, and Google Pay are activated, and display trust badges "
                        "(30-day money-back guarantee, SSL security) clearly in checkout footer."
                    ),
                    business_reason=(
                        "Accelerated checkouts eliminate 80% of form-field friction, recovering high-intent customers."
                    ),
                    implementation_effort="low",
                    confidence_level="high",
                    risks_or_prerequisites=[
                        "Requires Shopify Payments or compatible gateway credentials.",
                    ],
                    metric_to_monitor="purchase_rate",
                )
            )

        else:
            items.append(
                RecommendationItem(
                    title=f"Optimize Conversion Flow for {product_name}",
                    target_stage="product_page",
                    expected_direction="increase",
                    detected_problem=f"Conversion leak observed for {product_name} on {context.get('metric_affected')}.",
                    suggested_action="Review product presentation, pricing, and checkout pathway.",
                    business_reason="Aligns product experience with customer expectations to improve funnel progression.",
                    implementation_effort="medium",
                    confidence_level="medium",
                    risks_or_prerequisites=[],
                    metric_to_monitor=context.get("metric_affected", "conversion_rate"),
                )
            )

        return items
