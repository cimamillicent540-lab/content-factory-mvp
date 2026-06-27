"""Local static client/product profiles for the MVP."""


SPIKEX_BRAZIL_PROFILE = {
    "profile_id": "spikex_brazil",
    "client_name": "Spikex",
    "product": "Spikex",
    "industry": "crypto exchange",
    "platform": "Facebook Ads",
    "country": "Brazil",
    "language": "Brazilian Portuguese",
    "audience": "Brazilian retail traders interested in crypto, stocks, copy trading and AI trading tools",
    "selling_points": [
        "AI copy trading",
        "crypto trading",
        "US stocks trading",
        "fast onboarding",
        "beginner-friendly trading experience",
    ],
    "campaign_rules": [
        "Avoid unrealistic financial promises",
        "Avoid exaggerated claims",
        "Follow platform ad policy",
        "Include risk-aware language",
        "Campaign rules are for compliance context only and should not be copied directly into ad scripts",
    ],
    "forbidden_claims": [
        "guaranteed profit",
        "risk-free",
        "no loss",
        "guaranteed income",
        "win every trade",
        "easy money",
    ],
    "product_facts": [
        "Spikex is positioned as a trading platform",
        "The product may include AI copy trading messaging",
        "The product may include crypto trading messaging",
        "The product may include US stocks trading messaging",
        "Use modest, factual, risk-aware descriptions",
        "Do not claim guaranteed results",
        "Do not imply trading is risk-free",
    ],
    "default_demand": "Generate 5 short video ad concepts with hooks, scripts, voiceover, captions, Facebook ad copy, Runway prompts and ElevenLabs prompts",
}


_PROFILES = {SPIKEX_BRAZIL_PROFILE["profile_id"]: SPIKEX_BRAZIL_PROFILE}


def list_product_profiles():
    return [dict(profile) for profile in _PROFILES.values()]


def get_product_profile(profile_id):
    profile = _PROFILES.get(profile_id)
    return dict(profile) if profile else None


def profile_to_generation_request(profile_id):
    profile = get_product_profile(profile_id)
    if profile is None:
        return None
    return {
        "profile_id": profile["profile_id"],
        "客户": profile["client_name"],
        "行业": profile["industry"],
        "产品": profile["product"],
        "投放平台": profile["platform"],
        "国家": profile["country"],
        "语言": profile["language"],
        "目标人群": profile["audience"],
        "卖点": ", ".join(profile["selling_points"]),
        "活动规则": "; ".join(profile["campaign_rules"]),
        "限制词": ", ".join(profile["forbidden_claims"]),
        "需求": profile["default_demand"],
        "product_facts": list(profile["product_facts"]),
        "素材": [
            {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
            {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
            {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
        ],
    }
