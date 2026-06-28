"""Application-layer creative tracking and launch brief helpers."""

import copy
import re
from datetime import date


def build_product_code(product):
    normalized = (product or "").strip().lower()
    if normalized == "spikex":
        return "SPK"
    return _alpha_code(product, 3, "XXX")


def build_country_code(country):
    normalized = (country or "").strip().lower()
    known = {"brazil": "BR", "united states": "US", "usa": "US", "us": "US"}
    return known.get(normalized) or _alpha_code(country, 2, "XX")


def build_platform_code(platform):
    normalized = (platform or "").strip().lower()
    known = {
        "facebook ads": "FB",
        "facebook": "FB",
        "tiktok ads": "TT",
        "tiktok": "TT",
        "kwai": "KW",
        "google ads": "GG",
        "google": "GG",
    }
    return known.get(normalized) or _alpha_code(platform, 2, "XX")


def build_creative_id(product, country, platform, date, concept_index):
    return "-".join(
        [
            build_product_code(product),
            build_country_code(country),
            build_platform_code(platform),
            _compact_date(date),
            f"C{int(concept_index):03d}",
        ]
    )


def attach_creative_ids(concepts, product, country, platform, date=None):
    enriched = []
    for index, concept in enumerate(concepts or [], start=1):
        item = copy.deepcopy(concept)
        item["creative_id"] = build_creative_id(product, country, platform, date or _today(), index)
        enriched.append(item)
    return enriched


def build_media_buyer_launch_brief(summary, concepts):
    lines = [
        "# Media Buyer Launch Brief",
        "",
        "## Campaign Setup Summary",
        _line("product", summary.get("product")),
        _line("profile/client", summary.get("profile_id") or summary.get("client")),
        _line("platform", summary.get("platform")),
        _line("country", summary.get("country")),
        _line("language", summary.get("language")),
        _line("audience", summary.get("audience")),
        _line("campaign rules summary", summary.get("campaign_rules")),
        "",
        "## Creative Launch Table",
    ]
    for concept in concepts or []:
        lines.extend(
            [
                "",
                f"### {concept.get('creative_id', '')} {concept.get('concept_name', '')}".strip(),
                _line("creative_id", concept.get("creative_id")),
                _line("concept_name", concept.get("concept_name")),
                _line("target_angle", concept.get("target_angle")),
                _line("hook", concept.get("hook")),
                _line("recommended placement / platform", summary.get("platform")),
                _line("recommended test intent", "Test hook clarity, user fit, and risk-aware platform understanding."),
                _line("primary metric to watch", "CTR"),
                _line("secondary metrics to watch", "3s view rate, 50% view rate, registration, deposit, CPA"),
                _line("risk note", "Pause or rewrite if wording implies guaranteed profit, no risk, or unrealistic outcomes."),
            ]
        )
    lines.extend(
        [
            "",
            "## Launch Checklist",
            "- Confirm product facts",
            "- Confirm landing page matches ad claim",
            "- Confirm no guaranteed profit / no risk claim",
            "- Confirm video file name uses creative_id",
            "- Confirm captions match voiceover",
            "- Confirm Facebook copy matches approved brief",
            "- Confirm tracking / pixel / event setup before launch",
            "",
            "## Decision Rules",
            "- High CTR but low registration: check landing page / offer match",
            "- Low 3s view rate: improve first 3 seconds hook",
            "- High 3s view but low click: improve CTA or ad copy",
            "- High click but no deposit: review onboarding and trust signals",
            "- Compliance concern: pause and rewrite risky wording",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def _line(label, value):
    if value in (None, ""):
        return None
    if isinstance(value, list):
        value = " / ".join(str(item) for item in value)
    return f"- {label}: {value}"


def _alpha_code(value, length, fallback):
    chars = re.findall(r"[A-Za-z0-9]", value or "")
    if not chars:
        return fallback
    return "".join(chars[:length]).upper().ljust(length, "X")


def _compact_date(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    text = str(value or "").strip()
    match = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", text)
    if match:
        return "".join(match.groups())
    return _today().strftime("%Y%m%d")


def _today():
    return date.today()
