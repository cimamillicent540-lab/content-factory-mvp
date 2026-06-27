import json
import re

from content_factory.models import EVALUATION_WEIGHTS


class ProviderResponseError(ValueError):
    """Raised when an LLM provider returns unreadable or incomplete JSON."""


class MockAIProvider:
    """Deterministic local provider used before wiring a real LLM."""

    def structure_demand(self, raw_input, product_context):
        text = raw_input or ""
        platform = self._first_match(text, ("TikTok", "Facebook", "Instagram")) or product_context.get("platform") or "未指定"
        country = self._first_match(text, ("巴西", "美国", "墨西哥", "西班牙", "葡萄牙")) or product_context.get("country") or "未指定"
        duration = self._first_match(text, ("10秒", "15秒", "30秒")) or "15秒"
        audience = self._extract_audience(text, product_context)
        goal = "注册转化" if "注册" in text else "点击转化" if "点击" in text else "素材测试"
        scenario = "下班后用手机" if "下班" in text else "移动端浏览场景"
        missing_info = []
        if platform == "未指定":
            missing_info.append("平台")
        if country == "未指定":
            missing_info.append("国家")
        return {
            "平台": platform,
            "国家": country,
            "人群": audience,
            "场景": scenario,
            "目标": goal,
            "时长": duration,
            "输出物": ["素材方向", "脚本", "旁白", "字幕", "分镜", "视频Prompt", "广告文案"],
            "缺失信息": missing_info,
        }

    def deconstruct_benchmark(self, benchmark_input, product_context):
        source = benchmark_input.get("script_text") or benchmark_input.get("source_url") or "手动输入素材"
        return {
            "开头钩子": f"用一个和{product_context.get('name', '产品')}相关的真实使用问题开场。",
            "脚本节奏": "前3秒提出痛点，中段展示真实界面和卖点，结尾用明确行动指令收束。",
            "镜头结构": ["痛点场景", "产品界面", "核心卖点", "活动规则", "CTA"],
            "情绪路径": "困惑 -> 理解 -> 信任 -> 行动",
            "卖点表达": product_context.get("selling_points") or "围绕真实产品事实表达卖点",
            "CTA": "现在查看活动规则并完成下一步操作。",
            "可复用结构": "复用内容逻辑和镜头节奏，不复制具体产品、不虚构事实。",
            "来源摘要": source[:120],
        }

    def audit_materials(self, product, demand, materials):
        raw_input = demand.get("raw_input", "")
        forbidden_claims = self._forbidden_claims(product.get("forbidden_claims", ""))
        risk_text = " ".join(
            str(value or "")
            for value in (
                raw_input,
                product.get("name", ""),
                product.get("selling_points", ""),
            )
        ).lower()
        risks = [claim for claim in forbidden_claims if claim and claim.lower() in risk_text]
        if risks:
            return {
                "status": "FATAL_FAILED",
                "summary": "需求中包含产品禁用表达，禁止进入生成。",
                "checks": self._audit_checks(False, False, False),
                "missing_materials": [],
                "risks": risks,
                "risk_explanation": "命中收益保证、无风险或快速致富类表达，可能造成合规风险。",
                "替代表达建议": self._alternative_claims(risks),
                "next_actions": ["删除禁用表达", "重新提交符合合规边界的需求"],
            }
        required = ("真实logo", "真实界面", "真实活动规则")
        material_text = " ".join(
            f"{item.get('name', '')} {item.get('grade', '')} {item.get('notes', '')}"
            for item in materials
        )
        missing = [name for name in required if name not in material_text]
        non_compliant = [item.get("name", "未命名素材") for item in materials if not int(item.get("compliant", 1))]
        if non_compliant:
            return {
                "status": "FATAL_FAILED",
                "summary": "素材库中存在明确不合规素材，禁止进入生成。",
                "checks": self._audit_checks(True, not missing, False),
                "missing_materials": missing,
                "risks": [f"不合规素材：{name}" for name in non_compliant],
                "next_actions": ["移除或替换不合规素材", "重新执行素材评估"],
            }
        if missing:
            status = "HUMAN_REQUIRED" if "真实logo" in missing or "真实界面" in missing else "AUTO_REPAIR"
            return {
                "status": status,
                "summary": "红线素材仍有缺口，需要补齐后再生成。" if status == "HUMAN_REQUIRED" else "素材有轻微缺口，可先生成补充 brief。",
                "checks": self._audit_checks(True, False, True),
                "missing_materials": missing,
                "risks": [],
                "next_actions": [f"补充{name}" for name in missing],
            }
        return {
            "status": "PASS",
            "summary": "产品事实和红线素材足够，可进入内容生成。",
            "checks": self._audit_checks(True, True, True),
            "missing_materials": [],
            "risks": [],
            "next_actions": ["进入内容生成", "保留素材来源记录"],
        }

    def generate_content(self, product, demand, materials, benchmarks, audit):
        structured = demand.get("structured", {})
        language = self._normalize_language(structured.get("语言", "zh"))
        product_name = product.get("name", "该产品")
        audience = structured.get("人群") or self._extract_audience(demand.get("raw_input", ""), product)
        scene = self._localized_scene(language, structured.get("场景", "移动端使用场景"))
        goal = self._localized_goal(language, structured.get("目标", "转化"))
        selling_points = self._localized_points(language, product.get("selling_points") or "真实卖点")
        campaign_rules = product.get("campaign_rules") or "以落地页真实活动规则为准"
        benchmark_hint = self._localized_benchmark_hint(language)
        if benchmarks:
            benchmark_hint = benchmarks[0].get("可复用结构") or benchmark_hint
        forbidden_check = self._forbidden_claims_check(product, demand)
        return {
            "campaign_summary": {
                "产品": product_name,
                "国家": structured.get("国家") or product.get("country", ""),
                "平台": structured.get("平台") or product.get("platform", ""),
                "目标人群": audience,
                "投放语言": language,
                "核心卖点": selling_points,
                "风险提醒": "仅使用已确认产品事实和真实活动规则，不承诺收益、不暗示无风险。",
            },
            "video_ad_concepts": self._video_ad_concepts(
                language,
                product_name,
                audience,
                scene,
                goal,
                selling_points,
                campaign_rules,
                benchmark_hint,
            ),
            "scoring_report": {
                "hook_score": 15,
                "clarity_score": 15,
                "trust_score": 15,
                "compliance_score": 18,
                "localization_score": 14,
                "conversion_potential_score": 13,
                "total_score": 90,
                "improvement_suggestions": [
                    "前3秒保留真实界面或明确使用场景，避免抽象卖点堆叠。",
                    "每套素材只强调一个核心转化动作，降低信息密度。",
                    "投放后按 CTR、CPA、3秒播放率和50%播放率筛选下一轮脚本。",
                ],
            },
            "media_production_notes": {
                "Runway 生成建议": "使用真实产品界面截图做参考，镜头保持移动端竖屏、干净背景、轻快节奏。",
                "ElevenLabs 配音建议": "语速中等，可信克制，不使用夸张促销语气。",
                "字幕节奏建议": "每条字幕控制在两行内，首3秒出现核心场景和动作词。",
                "首 3 秒优化建议": "先给出用户问题或真实界面动作，再出现产品名。",
                "素材 A/B 测试建议": "测试痛点开场、界面开场、规则透明开场三类 hook。",
            },
            "launch_plan": {
                "推荐优先测试": ["C01", "C02", "C04"],
                "为什么先测": "这三套分别覆盖痛点、真实界面和活动规则透明度，能快速判断用户信任与转化阻力。",
                "每套适合的受众角度": {
                    "C01": "首次接触产品、需要快速理解价值的新用户",
                    "C02": "重视真实界面和操作路径的谨慎用户",
                    "C04": "对活动规则敏感、需要先确认边界的用户",
                },
                "初始投放观察指标": ["CTR", "CPA", "3秒播放率", "50%播放率", "注册转化率"],
            },
            "forbidden_claims_check": forbidden_check,
        }

    def evaluate_generation(self, product, demand, generation, audit):
        status = audit.get("status", "PASS")
        scores = dict(EVALUATION_WEIGHTS)
        if status == "AUTO_REPAIR":
            scores["真实性与红线素材"] = 15
            scores["视频brief可执行性"] = 12
        elif status in ("HUMAN_REQUIRED", "FATAL_FAILED"):
            scores["真实性与红线素材"] = 5
            scores["合规与风险"] = 2
        total = sum(scores.values())
        return {
            "总分": total,
            "维度得分": scores,
            "修改建议": [
                "保留真实产品事实，不添加未经确认的承诺。",
                "优先补充真实logo、真实界面和活动规则截图。",
                "投放后根据CTR、CPA和播放完成率重剪开头三秒。",
            ],
            "失败原因": [] if total >= 80 else ["素材真实性或合规风险不足"],
            "下一步动作": "可以进入人工复核和视频工具生成 brief。" if total >= 80 else "先补齐红线素材并重新生成。",
        }

    def analyze_performance(self, generation, performance_log):
        ctr = float(performance_log.get("ctr", 0) or 0)
        cpa = float(performance_log.get("cpa", 0) or 0)
        play_3s = float(performance_log.get("play_3s", 0) or 0)
        play_50 = float(performance_log.get("play_50", 0) or 0)
        retention_50 = play_50 / play_3s if play_3s else 0
        if ctr >= 1.0 and (cpa == 0 or cpa <= 30):
            action = "保留并放大预算，同时测试相同结构的新开头。"
            judgment = "点击和成本表现较好。"
        elif retention_50 < 0.25:
            action = "重剪前3秒，强化痛点和真实界面露出。"
            judgment = "中段留存偏弱，开头承接不足。"
        else:
            action = "保留卖点结构，测试更直接的CTA和更短版本。"
            judgment = "表现中性，适合小步迭代。"
        return {
            "表现判断": judgment,
            "关键指标": {"CTR": ctr, "CPA": cpa, "50%播放留存": round(retention_50, 4)},
            "可能问题": ["开头吸引力不足"] if retention_50 < 0.25 else ["需要继续验证不同CTA"],
            "下一轮动作": action,
            "建议": "保留、重剪或停用需要结合至少一轮新增素材对照测试。",
        }

    def _audit_checks(self, facts_ok, redline_ok, compliance_ok):
        return {
            "产品事实是否准确": facts_ok,
            "红线素材是否缺失": not redline_ok,
            "包装/logo/界面/活动规则是否真实": redline_ok,
            "是否存在违规或夸大承诺": not compliance_ok,
            "是否需要人工补素材": not redline_ok,
        }

    def _split_claims(self, value):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]

    def _first_match(self, text, candidates):
        for candidate in candidates:
            if candidate in text:
                return candidate
        return None

    def _extract_audience(self, text, product_context):
        configured = product_context.get("audience") or product_context.get("目标人群")
        if configured:
            return configured
        parts = [part.strip() for part in (text or "").replace("，", ",").split(",") if part.strip()]
        if len(parts) >= 3:
            return parts[2]
        if "新用户" in (text or ""):
            return "新用户"
        return "目标用户"

    def _normalize_language(self, value):
        normalized = (value or "zh").strip().lower()
        if normalized in ("pt-br", "pt_br", "portuguese-br", "portuguese br", "brazilian portuguese", "巴西葡萄牙语"):
            return "pt-BR"
        if normalized in ("es", "spanish", "español", "西班牙语"):
            return "es"
        if normalized in ("en", "english", "英语"):
            return "en"
        return "zh"

    def _localized_scene(self, language, scene):
        if scene in ("移动端浏览场景", "下班后用手机"):
            return {
                "pt-BR": "uso no celular",
                "es": "uso móvil",
                "en": "mobile browsing",
                "zh": scene,
            }[language]
        if language != "zh" and self._contains_chinese(scene):
            return {
                "pt-BR": "uso no celular",
                "es": "uso móvil",
                "en": "mobile browsing",
            }[language]
        return scene

    def _localized_goal(self, language, goal):
        if goal in ("注册转化", "转化"):
            return {
                "pt-BR": "cadastro",
                "es": "registro",
                "en": "signup",
                "zh": goal,
            }[language]
        if language != "zh" and self._contains_chinese(goal):
            return {
                "pt-BR": "cadastro",
                "es": "registro",
                "en": "signup",
            }[language]
        return goal

    def _localized_points(self, language, points):
        normalized = (points or "").strip().lower()
        if any(
            token in normalized
            for token in (
                "ai copy trading",
                "crypto and us stocks trading",
                "crypto trading",
                "us stocks trading",
                "fast onboarding",
                "beginner-friendly trading experience",
            )
        ):
            return {
                "pt-BR": "copy trading com IA, negociação de criptomoedas, negociação de ações dos EUA, cadastro rápido e experiência simples para iniciantes",
                "es": "copy trading con IA, negociación de criptomonedas, negociación de acciones de EE. UU., registro rápido y experiencia sencilla para principiantes",
                "en": "AI copy trading, crypto trading, US stocks trading, fast onboarding, and a beginner-friendly trading experience",
                "zh": "AI 跟单交易、加密货币交易、美股交易、快速开户和适合新手的交易体验",
            }[language]
        if any(token in normalized for token in ("fast deposits", "clean interface", "new user campaign", "signup reward", "copy trading", "quick start")):
            return {
                "pt-BR": "depósitos rápidos, interface clara e campanha para novos usuários",
                "es": "depósitos rápidos, interfaz clara y campaña para nuevos usuarios",
                "en": "fast deposits, clean interface, and a new user campaign",
                "zh": "到账快、界面清晰、新人活动",
            }[language]
        if "注册奖励" in points and "跟单" in points:
            return {
                "pt-BR": "bônus de cadastro, copy trading, início rápido",
                "es": "bono de registro, copy trading, inicio rápido",
                "en": "signup reward, copy trading, quick start",
                "zh": points,
            }[language]
        if points == "真实卖点":
            return {
                "pt-BR": "benefícios reais do produto",
                "es": "beneficios reales del producto",
                "en": "real product benefits",
                "zh": points,
            }[language]
        if language != "zh" and self._contains_chinese(points):
            return {
                "pt-BR": "benefícios reais do produto, interface clara e início simples",
                "es": "beneficios reales del producto, interfaz clara e inicio sencillo",
                "en": "real product benefits, a clear interface, and a simple start",
            }[language]
        return points

    def _contains_chinese(self, value):
        return bool(re.search(r"[一-鿿]", value or ""))

    def _localized_rules(self, language, rules):
        if "新人" in rules or "注册" in rules or "落地页" in rules:
            return {
                "pt-BR": "novos usuários podem participar após o cadastro; consulte a página para regras completas",
                "es": "los nuevos usuarios pueden participar después del registro; consulta la página para las reglas completas",
                "en": "new users can participate after signup; check the landing page for full terms",
                "zh": rules,
            }[language]
        return rules

    def _localized_benchmark_hint(self, language):
        return {
            "pt-BR": "Estrutura: dor primeiro, fatos depois, ação no final.",
            "es": "Estructura: dolor primero, hechos después, acción al final.",
            "en": "Structure: pain point first, facts next, action at the end.",
            "zh": "参考爆款结构：先痛点、再事实、后行动。",
        }[language]

    def _forbidden_claims(self, configured_claims=""):
        defaults = [
            "guaranteed profit",
            "risk-free",
            "no loss",
            "保证收益",
            "稳赚",
            "不亏钱",
            "100% win",
            "get rich quick",
        ]
        configured = self._split_claims(configured_claims or "")
        merged = []
        for claim in configured + defaults:
            if claim and claim not in merged:
                merged.append(claim)
        return merged

    def _alternative_claims(self, risks):
        suggestions = []
        for risk in risks:
            suggestions.append(f"将“{risk}”改为“请查看真实规则、产品功能和适合自己的使用场景”。")
        if not suggestions:
            suggestions.append("使用真实产品功能、活动规则和风险提示替代收益承诺。")
        return suggestions

    def _forbidden_claims_check(self, product, demand):
        text = " ".join(
            str(value or "")
            for value in (
                demand.get("raw_input", ""),
                product.get("name", ""),
                product.get("selling_points", ""),
            )
        ).lower()
        hits = [claim for claim in self._forbidden_claims(product.get("forbidden_claims", "")) if claim.lower() in text]
        return {
            "是否命中禁用词": bool(hits),
            "命中的词": hits,
            "风险说明": "命中收益保证、无风险或快速致富类表达。" if hits else "未命中预设高风险收益承诺表达。",
            "替代表达建议": self._alternative_claims(hits),
        }

    def _video_ad_concepts(self, language, product_name, audience, scene, goal, selling_points, campaign_rules, benchmark_hint):
        angles = self._localized_concept_angles(language)
        concepts = []
        for index, angle in enumerate(angles, start=1):
            concept_id = f"C{index:02d}"
            runway_prompt = angle["runway_prompt"].format(product=product_name, scene=scene, points=selling_points, hint=benchmark_hint)
            concepts.append(
                {
                    "concept_id": concept_id,
                    "concept_name": angle["name"],
                    "target_angle": angle["target_angle"].format(audience=audience),
                    "hook": angle["hook"].format(product=product_name, scene=scene, points=selling_points),
                    "scene_breakdown": angle["scene_breakdown"].format(product=product_name, scene=scene, points=selling_points),
                    "15s_script": angle["script"].format(product=product_name, scene=scene, points=selling_points),
                    "voiceover": angle["voiceover"].format(product=product_name, scene=scene, points=selling_points),
                    "captions": [caption.format(product=product_name, scene=scene, points=selling_points) for caption in angle["captions"]],
                    "visual_style": angle["visual_style"],
                    "runway_prompt": f"{runway_prompt} {self._runway_language_instruction(language)}",
                    "elevenlabs_prompt": angle["elevenlabs_prompt"],
                    "facebook_primary_text": angle["facebook_primary_text"].format(product=product_name, scene=scene, points=selling_points, rules=campaign_rules),
                    "facebook_headline": angle["facebook_headline"].format(product=product_name),
                    "facebook_description": angle["facebook_description"].format(product=product_name, points=selling_points),
                    "compliance_notes": f"只表达真实产品事实和页面活动规则；不承诺收益、不暗示无风险。活动规则仅供合规参考：{campaign_rules}",
                }
            )
        return concepts

    def _runway_language_instruction(self, language):
        return f"The voiceover, captions, on-screen text should be {self._language_label(language)}."

    def _language_label(self, language):
        return {
            "pt-BR": "Brazilian Portuguese",
            "es": "Spanish",
            "en": "English",
            "zh": "Chinese",
        }[language]

    def _localized_concept_angles(self, language):
        if language == "pt-BR":
            return [
                {
                    "name": "Comece conferindo as regras",
                    "target_angle": "Público: {audience}; novo usuário que precisa entender a oferta antes de agir",
                    "hook": "Confira {product} antes de participar.",
                    "scene_breakdown": "Celular em {scene}; interface real; destaque de {points}; tela final com regras.",
                    "script": "Abra com uma dúvida comum em {scene}. Mostre a interface real de {product}, explique {points} e finalize com um convite para conferir os detalhes.",
                    "voiceover": "Confira {product} com calma, veja a interface real e leia as regras antes de começar.",
                    "captions": ["Confira as regras reais", "{product}: {points}", "Comece pelos detalhes"],
                    "visual_style": "Vertical, mobile-first, clean UI close-ups",
                    "runway_prompt": "Brazilian Portuguese performance ad, real mobile UI, {scene}, show {product}, clear product flow, no exaggerated claims. {hint}",
                    "elevenlabs_prompt": "Brazilian Portuguese voiceover, calm, credible, natural rhythm.",
                    "facebook_primary_text": "Confira {product}: {points}. Veja as regras reais antes de participar. Comece pelos detalhes.",
                    "facebook_headline": "Confira {product}",
                    "facebook_description": "Veja regras e interface real antes de começar.",
                },
                {
                    "name": "Interface real em 15 segundos",
                    "target_angle": "Público: {audience}; usuário cauteloso que quer ver como funciona",
                    "hook": "Veja como {product} funciona no celular.",
                    "scene_breakdown": "Abertura com mão usando celular; zoom em interface; benefícios; CTA.",
                    "script": "Mostre a tela real, explique {points} em uma frase e conduza para conferir as regras completas.",
                    "voiceover": "Veja a interface, entenda os pontos principais e decida com base nas regras reais.",
                    "captions": ["Interface real", "{points}", "Confira antes de participar"],
                    "visual_style": "Screen-recording style with human hand context",
                    "runway_prompt": "Brazilian Portuguese mobile ad, hand holding phone, real interface beats, {product}, trustworthy pacing.",
                    "elevenlabs_prompt": "Brazilian Portuguese voice, concise and trustworthy.",
                    "facebook_primary_text": "Veja {product} em uso real no celular. {points}. Consulte as regras completas.",
                    "facebook_headline": "Veja como funciona",
                    "facebook_description": "Interface real e regras claras.",
                },
                {
                    "name": "Primeiro passo simples",
                    "target_angle": "Público: {audience}; usuário pronto para testar uma jornada curta",
                    "hook": "O primeiro passo em {product} pode ser simples.",
                    "scene_breakdown": "Problema rápido; tela do produto; regra da campanha; CTA.",
                    "script": "Mostre a situação, apresente {product}, destaque {points} e finalize com um CTA para conferir detalhes.",
                    "voiceover": "Comece conferindo os detalhes, a interface e as regras reais de {product}.",
                    "captions": ["Primeiro passo simples", "Leia as regras", "Confira os detalhes"],
                    "visual_style": "Fast cuts, clear captions, no hype",
                    "runway_prompt": "Brazilian Portuguese short ad, fast but clear cuts, real app UI, simple CTA, compliance-safe.",
                    "elevenlabs_prompt": "Brazilian Portuguese upbeat but restrained performance ad voice.",
                    "facebook_primary_text": "Comece por uma visão clara: {product}, {points} e regras reais da campanha.",
                    "facebook_headline": "Comece pelos detalhes",
                    "facebook_description": "Veja o fluxo antes de agir.",
                },
                {
                    "name": "Regras transparentes",
                    "target_angle": "Público: {audience}; usuário sensível a condições de campanha",
                    "hook": "Antes de participar, veja as regras.",
                    "scene_breakdown": "Tela de regras; interface; benefício; CTA para página.",
                    "script": "Comece com transparência, conecte {points} ao uso real e mantenha a decisão nas mãos do usuário.",
                    "voiceover": "As regras vêm primeiro. Confira os detalhes e veja se {product} faz sentido para você.",
                    "captions": ["Transparência primeiro", "Confira os detalhes", "Decida com clareza"],
                    "visual_style": "Transparent rule cards over real UI",
                    "runway_prompt": "Brazilian Portuguese transparent offer ad, rule cards, real UI, clear captions, trustworthy tone.",
                    "elevenlabs_prompt": "Brazilian Portuguese calm explanatory voice.",
                    "facebook_primary_text": "Regras claras antes de qualquer ação. Confira {product} e veja se combina com seu uso.",
                    "facebook_headline": "Regras claras",
                    "facebook_description": "Confira antes de participar.",
                },
                {
                    "name": "Comparação de rotina",
                    "target_angle": "Público: {audience}; usuário que decide no contexto do dia a dia",
                    "hook": "Em {scene}, uma interface clara ajuda.",
                    "scene_breakdown": "Rotina diária; celular; produto; resumo dos pontos; CTA.",
                    "script": "Use {scene} como contexto, mostre {product} e resuma {points} sem prometer resultado.",
                    "voiceover": "Na rotina, clareza importa. Veja {product}, confira {points} e leia as regras.",
                    "captions": ["Clareza na rotina", "{points}", "Sem promessas exageradas"],
                    "visual_style": "Lifestyle plus product UI",
                    "runway_prompt": "Brazilian Portuguese lifestyle mobile ad, daily routine, real app interface, credible tone.",
                    "elevenlabs_prompt": "Brazilian Portuguese lifestyle ad voice, natural and clear.",
                    "facebook_primary_text": "Em {scene}, confira {product}: {points}. Leia as regras e decida com clareza.",
                    "facebook_headline": "Clareza para começar",
                    "facebook_description": "Veja a interface e as regras.",
                },
            ]
        if language == "es":
            return [
                {
                    "name": "Consulta las reglas primero",
                    "target_angle": "Audiencia: {audience}; usuario nuevo que necesita entender la oferta",
                    "hook": "Consulta {product} antes de participar.",
                    "scene_breakdown": "Uso móvil en {scene}; interfaz real; {points}; cierre con reglas.",
                    "script": "Abre con una duda del usuario, muestra {product}, explica {points} y cierra invitando a revisar los detalles.",
                    "voiceover": "Consulta {product}, revisa la interfaz real y lee las reglas antes de comenzar.",
                    "captions": ["Consulta las reglas reales", "{product}: {points}", "Comienza por los detalles"],
                    "visual_style": "Vertical, interfaz clara, ritmo directo",
                    "runway_prompt": "Spanish performance ad, real mobile UI, {product}, clear offer rules, no exaggerated claims.",
                    "elevenlabs_prompt": "Spanish voiceover, natural, calm, credible.",
                    "facebook_primary_text": "Consulta {product}: {points}. Revisa las reglas reales antes de participar. Comienza por los detalles.",
                    "facebook_headline": "Consulta {product}",
                    "facebook_description": "Interfaz real y reglas claras.",
                },
                {
                    "name": "Interfaz real",
                    "target_angle": "Audiencia: {audience}; usuario cauteloso que quiere ver el flujo",
                    "hook": "Mira cómo funciona {product} en el móvil.",
                    "scene_breakdown": "Mano con móvil; interfaz; beneficio; CTA.",
                    "script": "Muestra la pantalla real, resume {points} y guía al usuario a revisar las reglas completas.",
                    "voiceover": "Mira la interfaz, entiende los puntos principales y decide con reglas reales.",
                    "captions": ["Interfaz real", "{points}", "Consulta antes de participar"],
                    "visual_style": "Screen recording con contexto humano",
                    "runway_prompt": "Spanish mobile ad, real phone interface, trustworthy pacing, {product}.",
                    "elevenlabs_prompt": "Spanish concise credible voice.",
                    "facebook_primary_text": "Mira {product} en uso real. {points}. Consulta las reglas completas.",
                    "facebook_headline": "Mira cómo funciona",
                    "facebook_description": "Reglas claras antes de empezar.",
                },
                {
                    "name": "Primer paso simple",
                    "target_angle": "Audiencia: {audience}; usuario que necesita una acción clara",
                    "hook": "El primer paso en {product} puede ser simple.",
                    "scene_breakdown": "Problema rápido; producto; regla; CTA.",
                    "script": "Presenta la situación, muestra {product}, destaca {points} y cierra con revisar detalles.",
                    "voiceover": "Comienza revisando los detalles, la interfaz y las reglas reales de {product}.",
                    "captions": ["Primer paso simple", "Lee las reglas", "Revisa los detalles"],
                    "visual_style": "Cortes rápidos con subtítulos claros",
                    "runway_prompt": "Spanish short ad, fast clean cuts, real app UI, simple CTA, compliance-safe.",
                    "elevenlabs_prompt": "Spanish upbeat but restrained ad voice.",
                    "facebook_primary_text": "Comienza con una visión clara: {product}, {points} y reglas reales.",
                    "facebook_headline": "Comienza por detalles",
                    "facebook_description": "Revisa el flujo antes de actuar.",
                },
                {
                    "name": "Reglas transparentes",
                    "target_angle": "Audiencia: {audience}; usuario sensible a condiciones",
                    "hook": "Antes de participar, revisa las reglas.",
                    "scene_breakdown": "Tarjetas de reglas; interfaz; beneficio; CTA.",
                    "script": "Presenta el contexto con transparencia, conecta con {points} y deja clara la decisión del usuario.",
                    "voiceover": "Las reglas van primero. Consulta los detalles y decide si {product} encaja contigo.",
                    "captions": ["Transparencia primero", "Revisa los detalles", "Decide con claridad"],
                    "visual_style": "Rule cards sobre UI real",
                    "runway_prompt": "Spanish transparent offer ad, rule cards, real UI, clear captions.",
                    "elevenlabs_prompt": "Spanish calm explanatory voice.",
                    "facebook_primary_text": "Reglas claras antes de actuar. Consulta {product} y decide con información.",
                    "facebook_headline": "Reglas claras",
                    "facebook_description": "Consulta antes de participar.",
                },
                {
                    "name": "Rutina diaria",
                    "target_angle": "Audiencia: {audience}; usuario que decide por contexto cotidiano",
                    "hook": "En {scene}, una interfaz clara ayuda.",
                    "scene_breakdown": "Rutina; móvil; producto; puntos clave; CTA.",
                    "script": "Usa {scene} como contexto, muestra {product} y resume {points} sin prometer resultados.",
                    "voiceover": "En la rutina, la claridad importa. Mira {product}, revisa {points} y lee las reglas.",
                    "captions": ["Claridad en tu rutina", "{points}", "Sin promesas exageradas"],
                    "visual_style": "Lifestyle con UI del producto",
                    "runway_prompt": "Spanish lifestyle mobile ad, daily routine, real app interface, credible tone.",
                    "elevenlabs_prompt": "Spanish natural lifestyle ad voice.",
                    "facebook_primary_text": "En {scene}, consulta {product}: {points}. Lee las reglas y decide con claridad.",
                    "facebook_headline": "Claridad para empezar",
                    "facebook_description": "Interfaz y reglas reales.",
                },
            ]
        if language == "en":
            return [
                {
                    "name": "Check the rules first",
                    "target_angle": "Audience: {audience}; new user who needs clarity before taking action",
                    "hook": "Check {product} before you join.",
                    "scene_breakdown": "Mobile use in {scene}; real interface; {points}; rules screen.",
                    "script": "Open with a user question, show {product}, explain {points}, then invite viewers to check the details.",
                    "voiceover": "Check {product}, review the real interface, and read the rules before you get started.",
                    "captions": ["Check the real rules", "{product}: {points}", "Get started with the details"],
                    "visual_style": "Vertical mobile-first ad with clean UI close-ups",
                    "runway_prompt": "English performance ad, real mobile UI, {product}, clear offer rules, no exaggerated claims.",
                    "elevenlabs_prompt": "English voiceover, calm, credible, natural rhythm.",
                    "facebook_primary_text": "Check {product}: {points}. Review the real rules before joining. Get started with the details.",
                    "facebook_headline": "Check {product}",
                    "facebook_description": "Real interface and clear rules.",
                },
                {
                    "name": "Real interface walkthrough",
                    "target_angle": "Audience: {audience}; cautious user who wants to see the flow",
                    "hook": "See how {product} works on mobile.",
                    "scene_breakdown": "Hand with phone; UI close-up; benefit; CTA.",
                    "script": "Show the real screen, summarize {points}, and guide users to review complete terms.",
                    "voiceover": "See the interface, understand the main points, and decide with the real rules in mind.",
                    "captions": ["Real interface", "{points}", "Check before joining"],
                    "visual_style": "Screen-recording style with human context",
                    "runway_prompt": "English mobile ad, hand holding phone, real interface beats, trustworthy pacing, {product}.",
                    "elevenlabs_prompt": "English concise credible performance voice.",
                    "facebook_primary_text": "See {product} in real mobile use. {points}. Check the complete rules first.",
                    "facebook_headline": "See how it works",
                    "facebook_description": "Clear rules before you start.",
                },
                {
                    "name": "Simple first step",
                    "target_angle": "Audience: {audience}; user who needs one clear action",
                    "hook": "Your first step with {product} can be simple.",
                    "scene_breakdown": "Quick problem; product screen; campaign rule; CTA.",
                    "script": "Show the situation, introduce {product}, highlight {points}, and close with a detail-check CTA.",
                    "voiceover": "Get started by checking the details, the interface, and the real rules for {product}.",
                    "captions": ["Simple first step", "Read the rules", "Check the details"],
                    "visual_style": "Fast cuts with clear captions",
                    "runway_prompt": "English short ad, fast clean cuts, real app UI, simple CTA, compliance-safe.",
                    "elevenlabs_prompt": "English upbeat but restrained ad voice.",
                    "facebook_primary_text": "Get started with a clear view: {product}, {points}, and real campaign rules.",
                    "facebook_headline": "Start with details",
                    "facebook_description": "Review the flow first.",
                },
                {
                    "name": "Transparent terms",
                    "target_angle": "Audience: {audience}; user sensitive to campaign conditions",
                    "hook": "Before joining, review the rules.",
                    "scene_breakdown": "Rule cards; interface; benefit; landing page CTA.",
                    "script": "Start with transparency, connect it to {points}, and keep the user's decision informed.",
                    "voiceover": "Rules come first. Check the details and decide whether {product} fits your use case.",
                    "captions": ["Transparency first", "Check the details", "Decide clearly"],
                    "visual_style": "Transparent rule cards over real UI",
                    "runway_prompt": "English transparent offer ad, rule cards, real UI, clear captions, trustworthy tone.",
                    "elevenlabs_prompt": "English calm explanatory voice.",
                    "facebook_primary_text": "Clear rules before any action. Check {product} and decide with real information.",
                    "facebook_headline": "Clear rules",
                    "facebook_description": "Check before joining.",
                },
                {
                    "name": "Daily routine context",
                    "target_angle": "Audience: {audience}; user deciding in an everyday mobile context",
                    "hook": "In {scene}, a clear interface helps.",
                    "scene_breakdown": "Daily routine; phone; product; key points; CTA.",
                    "script": "Use {scene} as context, show {product}, and summarize {points} without promising outcomes.",
                    "voiceover": "In your routine, clarity matters. Check {product}, review {points}, and read the rules.",
                    "captions": ["Clarity in your routine", "{points}", "No exaggerated promises"],
                    "visual_style": "Lifestyle plus product UI",
                    "runway_prompt": "English lifestyle mobile ad, daily routine, real app interface, credible tone.",
                    "elevenlabs_prompt": "English natural lifestyle ad voice.",
                    "facebook_primary_text": "In {scene}, check {product}: {points}. Read the rules and decide clearly.",
                    "facebook_headline": "Clarity to start",
                    "facebook_description": "See the interface and rules.",
                },
            ]
        return [
            {
                "name": "先看规则再行动",
                "target_angle": "受众：{audience}；需要先理解活动边界的新用户",
                "hook": "先看清{product}的真实规则。",
                "scene_breakdown": "{scene}打开手机；真实界面；{points}；活动规则收尾。",
                "script": "用用户疑问开场，展示{product}真实界面，说明{points}，最后提醒查看详情。",
                "voiceover": "先看{product}的真实界面和活动规则，再决定是否开始。",
                "captions": ["先看真实规则", "{product}：{points}", "现在查看详情"],
                "visual_style": "竖屏、移动端、真实界面特写",
                "runway_prompt": "中文投流广告，真实手机界面，展示{product}，节奏清晰，不夸大承诺。",
                "elevenlabs_prompt": "中文普通话旁白，可信、克制、清晰。",
                "facebook_primary_text": "{product}：{points}。先看真实界面和活动规则，再决定是否参与。",
                "facebook_headline": "查看{product}",
                "facebook_description": "真实界面和清晰规则。",
            },
            {
                "name": "真实界面演示",
                "target_angle": "受众：{audience}；重视操作路径的谨慎用户",
                "hook": "{product}在手机上可以这样看。",
                "scene_breakdown": "手持手机；界面演示；卖点说明；CTA。",
                "script": "展示真实屏幕，用一句话说明{points}，引导用户查看完整规则。",
                "voiceover": "看清界面、理解重点，再基于真实规则做决定。",
                "captions": ["真实界面", "{points}", "参与前先查看"],
                "visual_style": "录屏感结合真实使用场景",
                "runway_prompt": "中文移动端广告，手持手机，真实界面节奏，可信克制。",
                "elevenlabs_prompt": "中文简洁可信口播。",
                "facebook_primary_text": "看看{product}的真实使用路径。{points}，完整规则请以页面为准。",
                "facebook_headline": "看看如何使用",
                "facebook_description": "开始前先看规则。",
            },
            {
                "name": "简单第一步",
                "target_angle": "受众：{audience}；需要明确行动指引的用户",
                "hook": "{product}的第一步可以很清楚。",
                "scene_breakdown": "痛点；产品界面；规则；CTA。",
                "script": "先给出场景，再展示{product}，突出{points}，最后提示查看详情。",
                "voiceover": "先查看详情、界面和真实规则，再判断{product}是否适合你。",
                "captions": ["第一步很清楚", "先读规则", "查看详情"],
                "visual_style": "快节奏剪辑，字幕清晰",
                "runway_prompt": "中文短视频广告，真实App界面，清晰CTA，合规表达。",
                "elevenlabs_prompt": "中文轻快但克制的投流口播。",
                "facebook_primary_text": "从清楚的信息开始：{product}、{points}和真实活动规则。",
                "facebook_headline": "先看详情",
                "facebook_description": "行动前看清流程。",
            },
            {
                "name": "规则透明",
                "target_angle": "受众：{audience}；重视活动条件的用户",
                "hook": "参与前，先确认规则。",
                "scene_breakdown": "规则卡片；真实界面；卖点；落地页CTA。",
                "script": "先展示透明信息，再连接{points}，让用户基于信息做决定。",
                "voiceover": "规则先讲清楚。看看{product}是否符合你的使用场景。",
                "captions": ["透明信息优先", "先查看详情", "清楚再决定"],
                "visual_style": "规则卡片叠加真实界面",
                "runway_prompt": "中文透明活动规则广告，真实UI，字幕清晰，可信语气。",
                "elevenlabs_prompt": "中文解释型口播，平稳可信。",
                "facebook_primary_text": "先看规则，再看{product}。用真实信息做决定。",
                "facebook_headline": "规则清楚",
                "facebook_description": "参与前先确认。",
            },
            {
                "name": "日常场景切入",
                "target_angle": "受众：{audience}；在移动端日常场景中决策的用户",
                "hook": "{scene}，清楚的界面更重要。",
                "scene_breakdown": "日常场景；手机；产品；卖点；CTA。",
                "script": "以{scene}切入，展示{product}并说明{points}，不承诺任何结果。",
                "voiceover": "日常使用里，清楚和真实很重要。先看{product}、{points}和活动规则。",
                "captions": ["日常也要看清楚", "{points}", "不做夸大承诺"],
                "visual_style": "生活方式结合产品界面",
                "runway_prompt": "中文生活化移动端广告，真实产品界面，可信克制。",
                "elevenlabs_prompt": "中文自然生活化旁白。",
                "facebook_primary_text": "{scene}，可以这样了解{product}：{points}。先读规则再行动。",
                "facebook_headline": "清楚开始",
                "facebook_description": "看界面，看规则。",
            },
        ]

    def _localized_content(self, language, product_name, scene, goal, selling_points, campaign_rules, benchmark_hint):
        if language == "pt-BR":
            return {
                "素材方向": f"Mostre o valor real de {product_name} em {scene}, com foco em {goal}.",
                "脚本": {
                    "10秒脚本": f"Abra com uma necessidade em {scene}, mostre a interface real de {product_name}, destaque {selling_points} e finalize com as regras da oferta.",
                    "15秒脚本": f"Nos 3 primeiros segundos, apresente a dúvida do usuário. Depois, mostre logo e interface reais de {product_name}, explique {selling_points} e cite a regra: {campaign_rules}.",
                    "30秒脚本": f"Conte a jornada em cinco partes: contexto, uso do produto, benefício, regra da campanha e CTA. Use apenas fatos confirmados sobre {product_name}.",
                },
                "旁白": f"Confira {product_name} com atenção às regras reais, à interface do produto e ao que faz sentido para o seu uso.",
                "字幕": [f"{scene}: confira as regras reais", f"{product_name}: {selling_points}", "A campanha segue as regras da página", "Comece conferindo os detalhes"],
                "分镜": [{"镜头": 1, "画面": scene, "目的": "Apresentar contexto e necessidade"}],
                "Runway Prompt": f"Brazilian Portuguese ad video, real mobile usage scene, show {product_name} interface, clear pacing, no exaggerated claims.",
                "HeyGen Prompt": f"Brazilian Portuguese spokesperson video, calm and credible tone, explain {product_name}: {selling_points}, remind users to check page rules.",
                "ElevenLabs Prompt": "Brazilian Portuguese voiceover, natural rhythm, credible, clear, not exaggerated, suitable for performance ads.",
                "Facebook广告文案": f"Confira {product_name}: {selling_points}. Veja a interface real e as regras antes de participar. Comece pelos detalhes.",
                "TikTok广告文案": f"Veja como {product_name} funciona em {scene}. Regras claras, interface real e próximo passo simples. {benchmark_hint}",
            }
        if language == "es":
            return {
                "素材方向": f"Muestra el valor real de {product_name} en {scene}, con foco en {goal}.",
                "脚本": {
                    "10秒脚本": f"Abre con una necesidad en {scene}, muestra la interfaz real de {product_name}, destaca {selling_points} y cierra con las reglas.",
                    "15秒脚本": f"En los primeros 3 segundos, presenta la duda del usuario. Luego muestra logo e interfaz reales de {product_name}, explica {selling_points} y cita la regla: {campaign_rules}.",
                    "30秒脚本": f"Cuenta la historia en cinco partes: contexto, uso del producto, beneficio, regla de campaña y CTA. Usa solo hechos confirmados de {product_name}.",
                },
                "旁白": f"Consulta {product_name} revisando las reglas reales, la interfaz del producto y si encaja con tu forma de uso.",
                "字幕": [f"{scene}: consulta las reglas reales", f"{product_name}: {selling_points}", "La campaña sigue las reglas de la página", "Comienza revisando los detalles"],
                "分镜": [{"镜头": 1, "画面": scene, "目的": "Presentar contexto y necesidad"}],
                "Runway Prompt": f"Spanish ad video, real mobile usage scene, show {product_name} interface, clear pacing, no exaggerated claims.",
                "HeyGen Prompt": f"Spanish spokesperson video, credible calm tone, explain {product_name}: {selling_points}, remind users to check page rules.",
                "ElevenLabs Prompt": "Spanish voiceover, natural rhythm, credible, clear, not exaggerated, suitable for performance ads.",
                "Facebook广告文案": f"Consulta {product_name}: {selling_points}. Revisa la interfaz real y las reglas antes de participar. Comienza por los detalles.",
                "TikTok广告文案": f"Así puedes revisar {product_name} en {scene}: reglas claras, interfaz real y próximo paso simple. Comienza por los detalles. {benchmark_hint}",
            }
        if language == "en":
            return {
                "素材方向": f"Show the real value of {product_name} in {scene}, focused on {goal}.",
                "脚本": {
                    "10秒脚本": f"Open with a need in {scene}, show the real {product_name} interface, highlight {selling_points}, and close with the offer rules.",
                    "15秒脚本": f"In the first 3 seconds, introduce the user's question. Then show the real logo and interface for {product_name}, explain {selling_points}, and state the rule: {campaign_rules}.",
                    "30秒脚本": f"Build five beats: context, product use, benefit, campaign rule, and CTA. Use only confirmed facts about {product_name}.",
                },
                "旁白": f"Check {product_name} by reviewing the real rules, the product interface, and whether it fits your use case.",
                "字幕": [f"{scene}: check the real rules", f"{product_name}: {selling_points}", "Campaign terms follow the landing page", "Get started by checking the details"],
                "分镜": [{"镜头": 1, "画面": scene, "目的": "Set context and user need"}],
                "Runway Prompt": f"English ad video, real mobile usage scene, show {product_name} interface, clear pacing, no exaggerated claims.",
                "HeyGen Prompt": f"English spokesperson video, calm credible tone, explain {product_name}: {selling_points}, remind users to check page rules.",
                "ElevenLabs Prompt": "English voiceover, natural rhythm, credible, clear, not exaggerated, suitable for performance ads. Get started with a confident but restrained tone.",
                "Facebook广告文案": f"Check {product_name}: {selling_points}. Review the real interface and rules before joining. Get started with the details.",
                "TikTok广告文案": f"See how {product_name} works in {scene}: clear rules, real interface, simple next step. {benchmark_hint}",
            }
        return {
            "素材方向": f"围绕{scene}展示{product_name}的真实使用价值，目标是{goal}。",
            "脚本": {
                "10秒脚本": f"开场点出{scene}的需求，展示{product_name}真实界面，强调{selling_points}，结尾提示查看活动规则。",
                "15秒脚本": f"前3秒提出用户困扰，中段用真实logo和界面展示{product_name}，说明{selling_points}，最后引用活动规则：{campaign_rules}。",
                "30秒脚本": f"用生活场景切入，拆成痛点、产品操作、卖点解释、活动规则、CTA五段；全程只表达{product_name}已确认事实，不做夸大承诺。",
            },
            "旁白": f"如果你也在{scene}需要更清晰的选择，可以看看{product_name}。重点看真实界面、真实规则和适合自己的操作路径。",
            "字幕": [f"{scene}，先看真实规则", f"{product_name}：{selling_points}", "活动以页面展示为准", "现在查看详情"],
            "分镜": [{"镜头": 1, "画面": scene, "目的": "建立人群和问题"}],
            "Runway Prompt": f"中文广告短视频，真实手机使用场景，展示{product_name}界面，不虚构收益，节奏清晰，画面干净。",
            "HeyGen Prompt": f"中文口播，语气可信克制，说明{product_name}的真实卖点：{selling_points}，提醒活动以页面规则为准。",
            "ElevenLabs Prompt": "中文普通话旁白，节奏自然，可信、清晰、不夸张，适合投流素材。",
            "Facebook广告文案": f"{product_name}适合关注{goal}的用户。先看真实界面和活动规则，再决定是否参与。",
            "TikTok广告文案": f"{scene}可以这样看{product_name}：真实界面、真实规则、重点清楚。{benchmark_hint}",
        }


class OpenAIProvider(MockAIProvider):
    """OpenAI-backed provider with the same public methods as MockAIProvider."""

    DEFAULT_MODEL = "gpt-4.1-mini"

    def __init__(self, api_key, model=None, client=None):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when CONTENT_FACTORY_PROVIDER=openai")
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.client = client or self._build_client(api_key)

    def structure_demand(self, raw_input, product_context):
        payload = {
            "raw_input": raw_input,
            "product_context": product_context,
            "required_schema": {
                "平台": "string",
                "国家": "string",
                "人群": "string",
                "场景": "string",
                "目标": "string",
                "时长": "string",
                "输出物": "array",
                "缺失信息": "array",
            },
        }
        result = self._request_json(
            "你是海外投流素材需求结构化助手。只返回 JSON，不要 Markdown。",
            payload,
        )
        return self._require_keys(result, ("平台", "国家", "人群", "场景", "目标", "时长", "输出物", "缺失信息"), "结构化需求")

    def deconstruct_benchmark(self, benchmark_input, product_context):
        payload = {
            "benchmark_input": benchmark_input,
            "product_context": product_context,
            "required_fields": ["开头钩子", "脚本节奏", "镜头结构", "情绪路径", "卖点表达", "CTA", "可复用结构", "来源摘要"],
        }
        result = self._request_json(
            "你是广告 benchmark 拆解助手。只返回结构化 JSON，不要 Markdown。",
            payload,
        )
        return self._require_keys(result, ("开头钩子", "脚本节奏", "镜头结构", "情绪路径", "卖点表达", "CTA", "可复用结构", "来源摘要"), "Benchmark 拆解")

    def generate_content(self, product, demand, materials, benchmarks, audit):
        if audit.get("status") in ("HUMAN_REQUIRED", "FATAL_FAILED"):
            risks = audit.get("risks") or audit.get("missing_materials", [])
            return {
                "status": "BLOCKED",
                "risks": risks,
                "risk_explanation": audit.get("risk_explanation") or audit.get("summary") or "素材审核未通过，禁止生成正式素材。",
                "safer_alternatives": audit.get("替代表达建议") or ["删除高风险表达，改用真实产品功能、活动规则和风险提示。"],
                "next_actions": audit.get("next_actions", ["修复素材或需求后重新审核"]),
                "forbidden_claims_check": {
                    "是否命中禁用词": bool(risks),
                    "命中的词": risks,
                    "风险说明": audit.get("risk_explanation") or audit.get("summary") or "素材审核未通过。",
                },
            }
        language = demand.get("structured", {}).get("语言", "zh")
        payload = {
            "language": language,
            "language_instruction": self._language_instruction(language),
            "product": product,
            "demand": demand,
            "materials": materials,
            "benchmarks": benchmarks,
            "audit": audit,
            "required_fields": [
                "campaign_summary",
                "video_ad_concepts",
                "scoring_report",
                "media_production_notes",
                "launch_plan",
                "forbidden_claims_check",
            ],
            "concept_required_fields": self._concept_required_keys(),
        }
        result = self._request_json(
            (
                "你是海外广告素材生成助手。输出必须是 JSON。字段名必须稳定。"
                "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须按 language 输出；"
                "后台评分、合规说明和风险说明可以中文。"
                "正常生成时必须返回 campaign_summary、video_ad_concepts、scoring_report、"
                "media_production_notes、launch_plan、forbidden_claims_check。"
                "video_ad_concepts 必须正好 5 套。"
            ),
            payload,
        )
        return self._validate_generation_payload(result)

    def evaluate_generation(self, product, demand, generation, audit):
        payload = {
            "product": product,
            "demand": demand,
            "generation": generation,
            "audit": audit,
            "weights": EVALUATION_WEIGHTS,
            "required_fields": ["总分", "维度得分", "修改建议", "失败原因", "下一步动作"],
        }
        result = self._request_json(
            "你是素材质量评分助手。请返回 100 分制评分 JSON，总分必须是整数。",
            payload,
        )
        return self._require_keys(result, ("总分", "维度得分", "修改建议", "失败原因", "下一步动作"), "100分评分报告")

    def analyze_performance(self, generation, performance_log):
        payload = {
            "generation": generation,
            "performance_log": performance_log,
            "required_fields": ["表现判断", "关键指标", "可能问题", "下一轮动作", "建议"],
        }
        result = self._request_json(
            "你是投放分析助手。请基于指标返回中文 JSON 投放分析建议。",
            payload,
        )
        return self._require_keys(result, ("表现判断", "关键指标", "可能问题", "下一轮动作", "建议"), "投放分析建议")

    def _build_client(self, api_key):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI provider requires the openai Python package to be installed.") from exc
        return OpenAI(api_key=api_key)

    def _request_json(self, instruction, payload):
        prompt = f"{instruction}\n\n输入 JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                text={"format": self._json_text_format()},
            )
        except Exception as exc:
            raise ProviderResponseError(f"OpenAI API call failed: {exc}") from exc
        text = self._response_text(response)
        return self._parse_json(text)

    def _json_text_format(self):
        return {
            "type": "json_schema",
            "name": "content_factory_json",
            "schema": self._json_schema(),
            "strict": False,
        }

    def _json_schema(self):
        return {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "campaign_summary": {"type": "object", "additionalProperties": True},
                "video_ad_concepts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {key: {} for key in self._concept_required_keys()},
                    },
                },
                "scoring_report": {"type": "object", "additionalProperties": True},
                "media_production_notes": {"type": "object", "additionalProperties": True},
                "launch_plan": {"type": "object", "additionalProperties": True},
                "forbidden_claims_check": {"type": "object", "additionalProperties": True},
                "平台": {"type": "string"},
                "国家": {"type": "string"},
                "人群": {"type": "string"},
                "场景": {"type": "string"},
                "目标": {"type": "string"},
                "时长": {"type": "string"},
                "输出物": {"type": "array"},
                "缺失信息": {"type": "array"},
            },
        }

    def _response_text(self, response):
        if isinstance(response, str):
            return response
        output_text = getattr(response, "output_text", None)
        if output_text is not None:
            return output_text
        try:
            return response.output[0].content[0].text
        except (AttributeError, IndexError, TypeError) as exc:
            raise ProviderResponseError("OpenAI response did not contain readable JSON text.") from exc

    def _parse_json(self, text):
        candidate = (text or "").strip()
        if not candidate:
            raise ProviderResponseError("OpenAI provider returned empty content.")
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
        if fenced:
            candidate = fenced.group(1).strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(f"OpenAI provider returned invalid JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ProviderResponseError("OpenAI provider returned JSON, but the top-level value was not an object.")
        return parsed

    def _require_keys(self, value, keys, label):
        if not isinstance(value, dict):
            raise ProviderResponseError(f"{label} must be a JSON object.")
        missing = [key for key in keys if key not in value]
        if missing:
            raise ProviderResponseError(f"{label} JSON missing required fields: {', '.join(missing)}")
        return value

    def _validate_generation_payload(self, result):
        self._require_keys(
            result,
            (
                "campaign_summary",
                "video_ad_concepts",
                "scoring_report",
                "media_production_notes",
                "launch_plan",
                "forbidden_claims_check",
            ),
            "素材内容",
        )
        concepts = result["video_ad_concepts"]
        if not isinstance(concepts, list):
            raise ProviderResponseError("素材内容 JSON field video_ad_concepts must be an array.")
        if len(concepts) != 5:
            raise ProviderResponseError("素材内容 JSON field video_ad_concepts must contain exactly 5 concepts.")
        for index, concept in enumerate(concepts):
            self._require_keys(concept, self._concept_required_keys(), f"video_ad_concepts[{index}]")
        return result

    def _concept_required_keys(self):
        return (
            "concept_id",
            "concept_name",
            "target_angle",
            "hook",
            "scene_breakdown",
            "15s_script",
            "voiceover",
            "captions",
            "visual_style",
            "runway_prompt",
            "elevenlabs_prompt",
            "facebook_primary_text",
            "facebook_headline",
            "facebook_description",
            "compliance_notes",
        )

    def _language_instruction(self, language):
        normalized = self._normalize_language(language)
        return {
            "pt-BR": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用巴西葡萄牙语。",
            "es": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用西班牙语。",
            "en": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用英语。",
            "zh": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用中文。",
        }[normalized]
