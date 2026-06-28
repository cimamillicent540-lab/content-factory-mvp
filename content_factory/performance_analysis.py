import csv
import io
import re


CREATIVE_ID_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{2,8}-[A-Z]{2}-[A-Z]{2}-\d{8}-C\d{3}(?![A-Z0-9])", re.IGNORECASE)


def parse_performance_csv(csv_text):
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    rows = []
    for row in reader:
        if not row:
            continue
        cleaned = {
            str(key).strip(): str(value).strip()
            for key, value in row.items()
            if key is not None and value is not None
        }
        if any(value for value in cleaned.values()):
            rows.append(cleaned)
    return rows


def extract_creative_id(row):
    for key in ("creative_id", "Creative ID", "creative id"):
        value = row.get(key)
        if value:
            return value.strip()

    for key in ("ad_name", "Ad Name", "campaign_name", "Campaign Name", "adset_name", "Ad Set Name"):
        value = row.get(key)
        if not value:
            continue
        match = CREATIVE_ID_PATTERN.search(value)
        if match:
            return match.group(0).upper()
    return None


def normalize_metrics(row):
    return {
        "spend": _number(_lookup(row, ("spend", "Spend", "amount_spent", "Amount Spent"))),
        "impressions": _number(_lookup(row, ("impressions", "Impressions"))),
        "clicks": _number(_lookup(row, ("clicks", "Clicks"))),
        "link_clicks": _number(_lookup(row, ("link_clicks", "Link Clicks", "link clicks"))),
        "registrations": _number(_lookup(row, ("registrations", "Registrations", "registration", "sign_ups", "Sign Ups"))),
        "deposits": _number(_lookup(row, ("deposits", "Deposits", "purchases", "Purchases", "purchase", "Purchase"))),
        "video_3s_views": _number(_lookup(row, ("video_3s_views", "Video 3s Views", "3s_views", "3-second video plays"))),
        "video_50_views": _number(_lookup(row, ("video_50_views", "Video 50% Views", "50% video views"))),
        "video_95_views": _number(_lookup(row, ("video_95_views", "Video 95% Views", "95% video views"))),
    }


def calculate_performance_metrics(rows):
    grouped = {}
    unmatched_rows = []
    for row in rows:
        creative_id = extract_creative_id(row)
        if not creative_id:
            unmatched_rows.append(row)
            continue
        metrics = normalize_metrics(row)
        bucket = grouped.setdefault(creative_id, _empty_metrics(creative_id))
        for key in (
            "spend",
            "impressions",
            "clicks",
            "link_clicks",
            "registrations",
            "deposits",
            "video_3s_views",
            "video_50_views",
            "video_95_views",
        ):
            bucket[key] += metrics[key]

    creatives = {}
    for creative_id, metrics in grouped.items():
        enriched = _enrich_metrics(metrics)
        classification = classify_creative_performance(enriched)
        enriched.update(classification)
        creatives[creative_id] = enriched

    return {
        "creatives": creatives,
        "summary": {
            "matched_creative_count": len(creatives),
            "unmatched_row_count": len(unmatched_rows),
            "total_spend": sum(item["total_spend"] for item in creatives.values()),
            "total_impressions": sum(item["impressions"] for item in creatives.values()),
            "total_clicks": sum(item["clicks"] for item in creatives.values()),
            "total_registrations": sum(item["registrations"] for item in creatives.values()),
            "total_deposits": sum(item["deposits"] for item in creatives.values()),
        },
        "unmatched_rows": unmatched_rows,
    }


def classify_creative_performance(metrics):
    spend = metrics.get("total_spend", 0)
    impressions = metrics.get("impressions", 0)
    ctr = metrics.get("ctr")
    video_3s_rate = metrics.get("video_3s_rate")
    registrations = metrics.get("registrations", 0)
    deposits = metrics.get("deposits", 0)

    if spend < 5 or impressions < 1000:
        return {
            "recommendation": "INSUFFICIENT_DATA",
            "reason": "Not enough spend or impressions to judge the creative.",
            "action": "Keep collecting delivery data before making a cut decision.",
        }
    if _lt(ctr, 0.005) and _lt(video_3s_rate, 0.08):
        return {
            "recommendation": "NEEDS_RECUT",
            "reason": "Low CTR and weak first 3 seconds retention suggest the opening hook needs a recut.",
            "action": "Rewrite the first 3 seconds, simplify the visual proof, and test a sharper hook.",
        }
    if _gte(video_3s_rate, 0.15) and _lt(ctr, 0.008):
        return {
            "recommendation": "NEEDS_COPY_OR_CTA_TEST",
            "reason": "Viewers stay long enough to watch, but click intent is weak.",
            "action": "Test stronger CTA, benefit framing, and headline variants.",
        }
    if _gte(ctr, 0.02) and registrations == 0:
        return {
            "recommendation": "CHECK_LANDING_PAGE",
            "reason": "CTR is healthy but registrations are missing, so the click-to-signup path may be leaking.",
            "action": "Review landing page match, onboarding friction, tracking, and offer clarity.",
        }
    if registrations > 0 and deposits == 0 and spend >= 50:
        return {
            "recommendation": "CHECK_ONBOARDING_OR_TRUST",
            "reason": "Registrations exist but deposits or purchases are absent after meaningful spend.",
            "action": "Check trust signals, KYC/payment friction, deposit flow, and post-registration messaging.",
        }
    if _gte(ctr, 0.015) and registrations >= 3 and deposits >= 1:
        return {
            "recommendation": "SCALE_CANDIDATE",
            "reason": "Creative has enough click quality, registrations, and deposit signal to scale cautiously.",
            "action": "Increase budget gradually and create close variants around the same hook and angle.",
        }
    if _lt(ctr, 0.006) and spend >= 30:
        return {
            "recommendation": "PAUSE",
            "reason": "Spend is meaningful but click response remains weak.",
            "action": "Pause this version and rework the core angle before spending more.",
        }
    return {
        "recommendation": "KEEP_TESTING",
        "reason": "Performance is not decisive yet, but it has enough signal to continue controlled testing.",
        "action": "Keep the creative in a small test cell and compare against stronger variants.",
    }


def build_performance_summary(aggregated_metrics):
    creatives = aggregated_metrics.get("creatives", {})
    values = list(creatives.values())
    return {
        "total_creatives_matched": len(values),
        "missing_creative_id_rows_count": aggregated_metrics.get("summary", {}).get("unmatched_row_count", 0),
        "total_spend": aggregated_metrics.get("summary", {}).get("total_spend", 0),
        "best_creative_by_ctr": _best(values, "ctr"),
        "best_creative_by_registrations": _best(values, "registrations"),
        "best_creative_by_deposits": _best(values, "deposits"),
        "creatives_to_scale": _ids_by_recommendation(values, "SCALE_CANDIDATE"),
        "creatives_to_keep_testing": _ids_by_recommendation(values, "KEEP_TESTING"),
        "creatives_to_recut": _ids_by_recommendation(values, "NEEDS_RECUT"),
        "creatives_to_pause": _ids_by_recommendation(values, "PAUSE"),
        "internal_action_notes": [
            "Low 3s view rate usually means the first scene or hook needs a recut.",
            "High CTR with low registration usually points to landing page, offer, tracking, or onboarding issues.",
            "Scale only after checking creative wording, product facts, and risk-aware compliance language.",
        ],
    }


def _lookup(row, aliases):
    for alias in aliases:
        if alias in row:
            return row[alias]
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        value = lowered.get(alias.lower())
        if value is not None:
            return value
    return ""


def _number(value):
    if value in (None, ""):
        return 0
    cleaned = str(value).replace(",", "").replace("$", "").replace("%", "").strip()
    if not cleaned:
        return 0
    try:
        return float(cleaned)
    except ValueError:
        return 0


def _empty_metrics(creative_id):
    return {
        "creative_id": creative_id,
        "spend": 0,
        "impressions": 0,
        "clicks": 0,
        "link_clicks": 0,
        "registrations": 0,
        "deposits": 0,
        "video_3s_views": 0,
        "video_50_views": 0,
        "video_95_views": 0,
    }


def _enrich_metrics(metrics):
    enriched = dict(metrics)
    enriched["total_spend"] = enriched.pop("spend")
    enriched["ctr"] = _safe_div(enriched["clicks"], enriched["impressions"])
    enriched["link_ctr"] = _safe_div(enriched["link_clicks"], enriched["impressions"])
    enriched["cpc"] = _safe_div(enriched["total_spend"], enriched["clicks"])
    enriched["cpm"] = None if not enriched["impressions"] else enriched["total_spend"] / enriched["impressions"] * 1000
    enriched["cpa_registration"] = _safe_div(enriched["total_spend"], enriched["registrations"])
    enriched["cpa_deposit"] = _safe_div(enriched["total_spend"], enriched["deposits"])
    enriched["video_3s_rate"] = _safe_div(enriched["video_3s_views"], enriched["impressions"])
    enriched["video_50_retention"] = _safe_div(enriched["video_50_views"], enriched["video_3s_views"])
    enriched["video_95_retention"] = _safe_div(enriched["video_95_views"], enriched["video_3s_views"])
    return enriched


def _safe_div(numerator, denominator):
    return None if not denominator else numerator / denominator


def _lt(value, threshold):
    return value is not None and value < threshold


def _gte(value, threshold):
    return value is not None and value >= threshold


def _best(values, key):
    candidates = [item for item in values if item.get(key) is not None]
    if not candidates:
        return None
    best = max(candidates, key=lambda item: item.get(key) or 0)
    return {"creative_id": best["creative_id"], key: best.get(key)}


def _ids_by_recommendation(values, recommendation):
    return [item["creative_id"] for item in values if item.get("recommendation") == recommendation]
