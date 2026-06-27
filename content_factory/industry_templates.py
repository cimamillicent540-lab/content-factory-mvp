"""Industry templates used to shape deterministic mock output and LLM prompts."""


CRYPTO_EXCHANGE_TEMPLATE = {
    "name": "Crypto Exchange / Trading V1",
    "match_keywords": ["crypto exchange", "exchange", "trading", "crypto"],
    "approved_angles": [
        "beginner education angle",
        "AI copy trading discovery angle",
        "platform walkthrough angle",
        "market access angle",
        "risk-aware trading angle",
        "app onboarding angle",
        "trading habit / daily check angle",
        "feature comparison angle",
    ],
    "banned_or_high_risk_claims": [
        "guaranteed profit",
        "risk-free",
        "no loss",
        "稳赚",
        "保证收益",
        "不亏钱",
        "100% win",
        "get rich quick",
        "financial freedom guaranteed",
        "easy money",
        "profit promise",
        "win every trade",
    ],
    "safer_phrases": [
        "explore market tools",
        "understand platform features",
        "review trading rules",
        "trade with risk awareness",
        "learn before trading",
        "compare market information",
        "manage your own trading decisions",
        "educational and informational use",
    ],
    "brazilian_portuguese_terms": {
        "AI copy trading": "copy trading com IA",
        "crypto trading": "negociação de criptomoedas",
        "US stocks trading": "negociação de ações dos EUA",
        "fast onboarding": "cadastro rápido",
        "beginner-friendly trading experience": "experiência simples para iniciantes",
        "trading tools": "ferramentas de negociação",
        "market access": "acesso ao mercado",
        "risk-aware trading": "negociação com consciência de risco",
        "platform walkthrough": "demonstração da plataforma",
        "educational content": "conteúdo educativo",
    },
    "video_style_guidance": [
        "UGC-style phone screen walkthrough",
        "simple app interface close-up",
        "Brazilian creator speaking to camera",
        "fast first 3 seconds hook",
        "subtitle-first vertical video",
        "clean mobile-first layout",
        "no luxury lifestyle claims",
        "no cash piles",
        "no guaranteed profit visuals",
        "no exaggerated wealth imagery",
    ],
    "copywriting_rules": [
        "avoid profit promises",
        "avoid risk-free wording",
        "avoid urgency pressure like earn now",
        "avoid luxury lifestyle implications",
        "emphasize product features, education, onboarding, and risk awareness",
        "keep claims factual and modest",
        "use soft CTAs such as Explore features, Learn how it works, Check the rules",
    ],
}


def detect_industry_template(product, demand=None):
    """Return the industry template for the product/demand context, if any."""
    product = product or {}
    demand = demand or {}
    structured = demand.get("structured", {}) if isinstance(demand, dict) else {}
    haystack = " ".join(
        str(value or "")
        for value in (
            product.get("category", ""),
            product.get("industry", ""),
            demand.get("raw_input", "") if isinstance(demand, dict) else "",
            structured.get("行业", ""),
            structured.get("品类", ""),
        )
    ).lower()
    if any(keyword in haystack for keyword in CRYPTO_EXCHANGE_TEMPLATE["match_keywords"]):
        return CRYPTO_EXCHANGE_TEMPLATE
    return None


def template_guidance_text(template):
    if not template:
        return ""
    return (
        f"{template['name']}: use approved angles {template['approved_angles']}; "
        f"avoid high-risk claims {template['banned_or_high_risk_claims']}; "
        f"prefer safer phrases {template['safer_phrases']}; "
        f"Brazilian Portuguese terms {template['brazilian_portuguese_terms']}; "
        f"video style guidance {template['video_style_guidance']}; "
        f"copywriting rules {template['copywriting_rules']}; "
        "forbidden_claims and campaign_rules are compliance references, not formal ad claims."
    )
