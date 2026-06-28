def build_next_round_brief_request(performance_report, recommendations):
    structured = _build_structured_request(performance_report, recommendations)
    return {
        "markdown": _request_markdown(structured),
        "structured": structured,
    }


def _build_structured_request(performance_report, recommendations):
    all_items = []
    for key in ("scale_candidates", "needs_recut", "copy_or_cta_tests", "landing_page_checks", "pause", "keep_testing"):
        all_items.extend(recommendations.get(key, []))

    priority_actions = {"High": [], "Medium": [], "Low": []}
    for item in all_items:
        priority = item.get("priority") or "Medium"
        priority_actions.setdefault(priority, []).append(_action_payload(item))

    generation_requests = _generation_requests(recommendations)
    suggested_naming = _suggested_naming(recommendations)
    do_not_repeat = _do_not_repeat(recommendations)
    return {
        "objective": _objective(recommendations),
        "source_report": _source_report(performance_report),
        "priority_actions": priority_actions,
        "generation_requests": generation_requests,
        "do_not_repeat": do_not_repeat,
        "internal_production_notes": [
            "Keep Creative ID lineage in file names.",
            "Use variant suffixes such as V2A / V2B / V2C.",
            "Keep product facts consistent with approved profile and landing page.",
            "Confirm landing page message match before launch.",
            "Keep risk-aware language for trading products.",
            "Do not imply guaranteed profit, risk-free trading, or guaranteed improvement.",
        ],
        "suggested_naming": suggested_naming,
    }


def _request_markdown(structured):
    lines = [
        "# Next Round Creative Brief Request",
        "",
        "## Next Round Objective",
    ]
    lines.extend(f"- {item}" for item in structured["objective"])

    source = structured["source_report"]
    lines.extend(
        [
            "",
            "## Source Performance Report",
            f"- report_id: {source.get('report_id')}",
            f"- created_at: {source.get('created_at')}",
            f"- matched creative count: {source.get('matched_creative_count')}",
            f"- total spend: {source.get('total_spend')}",
            f"- total impressions: {source.get('total_impressions')}",
            f"- total clicks: {source.get('total_clicks')}",
            f"- total registrations: {source.get('total_registrations')}",
            f"- total deposits / purchases: {source.get('total_deposits')}",
            "",
            "## Priority Creative Actions",
        ]
    )
    for priority in ("High", "Medium", "Low"):
        lines.extend(["", f"### {priority} priority"])
        actions = structured["priority_actions"].get(priority, [])
        if not actions:
            lines.append("- None for now.")
            continue
        for action in actions:
            lines.extend(
                [
                    f"- creative_id: {action.get('creative_id')}",
                    f"  previous recommendation: {action.get('previous_recommendation')}",
                    f"  reason: {action.get('reason')}",
                    f"  requested next action: {action.get('requested_next_action')}",
                    f"  requested variation type: {action.get('requested_variation_type')}",
                    f"  suggested output count: {action.get('suggested_output_count')}",
                    f"  notes for creative team: {action.get('notes_for_creative_team')}",
                ]
            )

    lines.extend(["", "## Next Round Generation Requests"])
    lines.extend(f"- {item}" for item in structured["generation_requests"])
    lines.extend(["", "## Do Not Repeat"])
    lines.extend(f"- {item}" for item in structured["do_not_repeat"])
    lines.extend(["", "## Internal Production Notes"])
    lines.extend(f"- {item}" for item in structured["internal_production_notes"])
    lines.extend(["", "## Suggested Naming"])
    lines.extend(f"- {item}" for item in structured["suggested_naming"])
    return "\n".join(lines)


def _objective(recommendations):
    objectives = []
    if recommendations.get("scale_candidates"):
        objectives.append("Expand winning angles with controlled variants.")
    if recommendations.get("needs_recut"):
        objectives.append("Recut weak hooks before relaunch.")
    if recommendations.get("copy_or_cta_tests"):
        objectives.append("Test clearer CTA and Facebook copy.")
    if recommendations.get("landing_page_checks"):
        objectives.append("Check landing page mismatch and improve onboarding / trust explanation.")
    if recommendations.get("keep_testing") and not recommendations.get("scale_candidates"):
        objectives.append("Continue low-budget testing if data is insufficient.")
    if not objectives:
        objectives.append("Prepare next-round variations conservatively based on current performance signals.")
    return objectives


def _source_report(performance_report):
    report_summary = performance_report.get("summary", {})
    aggregated_summary = performance_report.get("aggregated", {}).get("summary", {})
    return {
        "report_id": performance_report.get("report_id", ""),
        "created_at": performance_report.get("created_at", ""),
        "matched_creative_count": report_summary.get("total_creatives_matched") or aggregated_summary.get("matched_creative_count", 0),
        "total_spend": report_summary.get("total_spend", 0),
        "total_impressions": aggregated_summary.get("total_impressions", 0),
        "total_clicks": aggregated_summary.get("total_clicks", 0),
        "total_registrations": aggregated_summary.get("total_registrations", 0),
        "total_deposits": aggregated_summary.get("total_deposits", 0),
    }


def _action_payload(item):
    return {
        "creative_id": item.get("creative_id", ""),
        "previous_recommendation": item.get("current_recommendation", ""),
        "reason": item.get("reason", ""),
        "requested_next_action": item.get("next_action", ""),
        "requested_variation_type": item.get("suggested_variation", ""),
        "suggested_output_count": _output_count(item),
        "notes_for_creative_team": _team_note(item),
    }


def _output_count(item):
    recommendation = item.get("current_recommendation", "")
    if recommendation == "SCALE_CANDIDATE":
        return "3 variants"
    if recommendation == "NEEDS_RECUT":
        return "1-2 recut versions"
    if recommendation in ("CHECK_LANDING_PAGE", "CHECK_ONBOARDING_OR_TRUST"):
        return "1 message-match / trust version"
    if recommendation == "PAUSE":
        return "0 until angle is reworked"
    return "1 controlled variant"


def _team_note(item):
    recommendation = item.get("current_recommendation", "")
    if recommendation == "SCALE_CANDIDATE":
        return "Keep the core angle, preserve Creative ID lineage, and only change one major variable per variant."
    if recommendation == "NEEDS_RECUT":
        return "Focus on first 3 seconds, subtitle pacing, clearer product context, and faster visual proof."
    if recommendation in ("CHECK_LANDING_PAGE", "CHECK_ONBOARDING_OR_TRUST"):
        return "Align ad promise with landing page, onboarding, trust signals, and risk-aware explanation."
    if recommendation == "PAUSE":
        return "Do not scale this version; rework the core angle before any relaunch."
    return "Keep testing before scaling and prepare a small controlled variation."


def _generation_requests(recommendations):
    requests = []
    for item in recommendations.get("scale_candidates", []):
        cid = item.get("creative_id")
        requests.append(
            f"Generate 3 new variants based on {cid}. Keep the winning angle, but test stronger first 3-second hook, softer CTA, and more trust-building onboarding explanation."
        )
    for item in recommendations.get("needs_recut", []):
        cid = item.get("creative_id")
        requests.append(f"Recut {cid}. Focus on first 3 seconds, subtitle pacing, and clearer product context.")
    for item in recommendations.get("copy_or_cta_tests", []):
        cid = item.get("creative_id")
        requests.append(f"Create CTA / Facebook copy variants for {cid}. Keep visual structure stable and test clearer click intent.")
    for item in recommendations.get("landing_page_checks", []):
        cid = item.get("creative_id")
        requests.append(f"Create a message match, onboarding, and trust-building version for {cid} after landing page review.")
    if not requests:
        requests.extend(recommendations.get("creative_brief_requests", []))
    if not requests:
        requests.append("Prepare one conservative next-round variation after collecting more performance data.")
    return requests


def _do_not_repeat(recommendations):
    notes = [
        "Do not reuse weak first 3-second opening.",
        "Do not use vague CTA.",
        "Do not imply guaranteed profit.",
        "Do not use no-risk trading language.",
        "Do not scale paused creatives without a new test.",
    ]
    for item in recommendations.get("pause", []):
        notes.append(f"Do not relaunch {item.get('creative_id')} without reworking the core angle.")
    for item in recommendations.get("needs_recut", []):
        notes.append(f"Do not reuse the current opening of {item.get('creative_id')} without a recut.")
    return notes


def _suggested_naming(recommendations):
    names = []
    for item in recommendations.get("scale_candidates", []):
        cid = item.get("creative_id", "")
        names.extend([f"{cid}-V2A", f"{cid}-V2B", f"{cid}-V2C"])
    for item in recommendations.get("needs_recut", []):
        cid = item.get("creative_id", "")
        names.extend([f"{cid}-RECUT-V2A", f"{cid}-RECUT-V2B"])
    for item in recommendations.get("copy_or_cta_tests", []):
        cid = item.get("creative_id", "")
        names.extend([f"{cid}-CTA-V2A", f"{cid}-COPY-V2B"])
    for item in recommendations.get("landing_page_checks", []):
        cid = item.get("creative_id", "")
        names.append(f"{cid}-TRUST-V2A")
    return names or ["Use {CREATIVE_ID}-V2A for the first next-round controlled variant."]
