def build_next_round_recommendations(performance_report):
    creatives = performance_report.get("aggregated", {}).get("creatives", {})
    result = {
        "summary": {
            "report_id": performance_report.get("report_id", ""),
            "creative_count": len(creatives),
            "message": "Internal next-round guidance based on saved performance report signals.",
        },
        "scale_candidates": [],
        "keep_testing": [],
        "needs_recut": [],
        "copy_or_cta_tests": [],
        "landing_page_checks": [],
        "pause": [],
        "next_round_angles": [],
        "creative_brief_requests": [],
        "internal_notes": [
            "Use these recommendations as internal test planning guidance, not performance promises.",
            "Do not promise ROI, guaranteed CPA improvement, or guaranteed deposits.",
            "Check product facts, compliance wording, and landing page consistency before relaunch.",
        ],
    }

    for creative_id, metrics in creatives.items():
        recommendation = _effective_recommendation(metrics)
        item = _recommendation_item(creative_id, recommendation, metrics)
        _bucket(result, recommendation).append(item)

    _add_next_round_angles(result)
    _add_creative_brief_requests(result)
    if not creatives:
        result["next_round_angles"].append("Continue small-budget testing until there is enough data to identify directional winners.")
        result["creative_brief_requests"].append("Collect more delivery data before requesting new creative variations.")
    return result


def next_round_plan_markdown(recommendations):
    lines = [
        "# Next Round Creative Recommendations",
        "",
        "## Summary",
        f"- report_id: {recommendations.get('summary', {}).get('report_id', '')}",
        f"- creative_count: {recommendations.get('summary', {}).get('creative_count', 0)}",
        f"- note: {recommendations.get('summary', {}).get('message', '')}",
    ]
    sections = (
        ("Scale Candidates", "scale_candidates"),
        ("Keep Testing", "keep_testing"),
        ("Needs Recut", "needs_recut"),
        ("Copy / CTA Tests", "copy_or_cta_tests"),
        ("Landing Page Checks", "landing_page_checks"),
        ("Pause", "pause"),
    )
    for title, key in sections:
        lines.extend(["", f"## {title}"])
        items = recommendations.get(key, [])
        if not items:
            lines.append("- None for now.")
            continue
        for item in items:
            lines.extend(
                [
                    f"- creative_id: {item.get('creative_id')}",
                    f"  current_recommendation: {item.get('current_recommendation')}",
                    f"  priority: {item.get('priority')}",
                    f"  reason: {item.get('reason')}",
                    f"  next_action: {item.get('next_action')}",
                    f"  suggested_variation: {item.get('suggested_variation')}",
                ]
            )
    lines.extend(["", "## Next Round Angles"])
    lines.extend(f"- {item}" for item in recommendations.get("next_round_angles", []))
    lines.extend(["", "## creative_brief_requests"])
    lines.extend(f"- {item}" for item in recommendations.get("creative_brief_requests", []))
    lines.extend(["", "## Internal Notes"])
    lines.extend(f"- {item}" for item in recommendations.get("internal_notes", []))
    return "\n".join(lines)


def _effective_recommendation(metrics):
    ctr = metrics.get("ctr")
    video_3s_rate = metrics.get("video_3s_rate")
    registrations = metrics.get("registrations", 0)
    deposits = metrics.get("deposits", 0)
    recommendation = metrics.get("recommendation", "KEEP_TESTING")
    if _lt(ctr, 0.005) and _lt(video_3s_rate, 0.08):
        return "NEEDS_RECUT"
    if _gte(ctr, 0.02) and registrations == 0:
        return "CHECK_LANDING_PAGE"
    if _gte(video_3s_rate, 0.15) and _lt(ctr, 0.008):
        return "NEEDS_COPY_OR_CTA_TEST"
    if _gte(ctr, 0.02) and deposits == 0:
        return "CHECK_ONBOARDING_OR_TRUST"
    return recommendation


def _recommendation_item(creative_id, recommendation, metrics):
    templates = {
        "SCALE_CANDIDATE": {
            "next_action": "Create 2-3 controlled variations before increasing budget.",
            "suggested_variation": "Keep the same angle, test a stronger first 3-second hook and alternate CTA.",
            "priority": "High",
        },
        "KEEP_TESTING": {
            "next_action": "Keep testing in a small cell while preparing one controlled variant.",
            "suggested_variation": "Hold the core angle steady and test one hook or caption change.",
            "priority": "Medium",
        },
        "NEEDS_RECUT": {
            "next_action": "Recut the hook before relaunch.",
            "suggested_variation": "Strengthen the first 3 seconds with clearer UGC opening, product proof, and faster visual context.",
            "priority": "High",
        },
        "NEEDS_COPY_OR_CTA_TEST": {
            "next_action": "Test clearer CTA and ad copy before changing the whole concept.",
            "suggested_variation": "Keep the visual flow but test benefit-first Facebook copy and softer CTA.",
            "priority": "Medium",
        },
        "CHECK_LANDING_PAGE": {
            "next_action": "Review landing page message match, registration flow, trust signals, and tracking.",
            "suggested_variation": "Create a landing page aligned version that repeats the clicked promise without adding risky claims.",
            "priority": "High",
        },
        "CHECK_ONBOARDING_OR_TRUST": {
            "next_action": "Review onboarding, trust signals, KYC/payment friction, and post-registration messaging.",
            "suggested_variation": "Create a trust-building onboarding version for users who clicked but did not deposit.",
            "priority": "Medium",
        },
        "PAUSE": {
            "next_action": "Pause for now and avoid spending more on this exact version.",
            "suggested_variation": "Rework the core angle before relaunching a new version.",
            "priority": "High",
        },
        "INSUFFICIENT_DATA": {
            "next_action": "Continue low-budget testing before judging the creative.",
            "suggested_variation": "Do not create many variants until the current version has enough impressions and spend.",
            "priority": "Low",
        },
    }
    template = templates.get(recommendation, templates["KEEP_TESTING"])
    return {
        "creative_id": creative_id,
        "current_recommendation": recommendation,
        "reason": metrics.get("reason") or _default_reason(recommendation),
        "next_action": template["next_action"],
        "suggested_variation": template["suggested_variation"],
        "priority": template["priority"],
    }


def _bucket(result, recommendation):
    if recommendation == "SCALE_CANDIDATE":
        return result["scale_candidates"]
    if recommendation == "NEEDS_RECUT":
        return result["needs_recut"]
    if recommendation == "NEEDS_COPY_OR_CTA_TEST":
        return result["copy_or_cta_tests"]
    if recommendation in ("CHECK_LANDING_PAGE", "CHECK_ONBOARDING_OR_TRUST"):
        return result["landing_page_checks"]
    if recommendation == "PAUSE":
        return result["pause"]
    return result["keep_testing"]


def _add_next_round_angles(result):
    if result["scale_candidates"]:
        result["next_round_angles"].append("Expand winning angle with 2-3 controlled variants before broader scaling.")
    if result["needs_recut"]:
        result["next_round_angles"].append("Improve first 3 seconds with sharper UGC hook, faster product context, and clearer visual opening.")
    if result["copy_or_cta_tests"]:
        result["next_round_angles"].append("Test clearer CTA, benefit-led Facebook copy, and lower-friction click language.")
    if result["landing_page_checks"]:
        result["next_round_angles"].append("Review landing page message match, registration flow, trust signals, and onboarding explanation.")
    if result["pause"]:
        result["next_round_angles"].append("Avoid repeating paused angles until the core promise, opening scene, or audience fit is reworked.")
    if result["keep_testing"] and not result["scale_candidates"]:
        result["next_round_angles"].append("Keep testing current angles with small changes before declaring a winner.")


def _add_creative_brief_requests(result):
    for item in result["scale_candidates"]:
        result["creative_brief_requests"].append(f"Create 2-3 controlled variants based on {item['creative_id']} using the same angle with new hook and CTA tests.")
    for item in result["needs_recut"]:
        result["creative_brief_requests"].append(f"Recut {item['creative_id']} with stronger first 3 seconds, clearer product proof, and faster opening rhythm.")
    for item in result["copy_or_cta_tests"]:
        result["creative_brief_requests"].append(f"Create copy and CTA variants for {item['creative_id']} while keeping the main visual sequence.")
    for item in result["landing_page_checks"]:
        result["creative_brief_requests"].append(f"Create a message-match and trust-building variant for {item['creative_id']} after landing page review.")
    for item in result["pause"]:
        result["creative_brief_requests"].append(f"Pause {item['creative_id']} for now and only brief a new version after the core angle is reworked.")
    if not result["creative_brief_requests"] and result["keep_testing"]:
        result["creative_brief_requests"].append("Keep current creatives in controlled testing and prepare one small hook/caption variant for comparison.")


def _default_reason(recommendation):
    return f"Current performance classification is {recommendation}; use this as an internal planning signal."


def _lt(value, threshold):
    return value is not None and value < threshold


def _gte(value, threshold):
    return value is not None and value >= threshold
