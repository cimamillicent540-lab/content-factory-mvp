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
        audience = "新用户" if "新" in text else "目标用户"
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
        forbidden_claims = self._split_claims(product.get("forbidden_claims", ""))
        risks = [claim for claim in forbidden_claims if claim and claim in raw_input]
        if risks:
            return {
                "status": "FATAL_FAILED",
                "summary": "需求中包含产品禁用表达，禁止进入生成。",
                "checks": self._audit_checks(False, False, False),
                "missing_materials": [],
                "risks": risks,
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
        scene = self._localized_scene(language, structured.get("场景", "移动端使用场景"))
        goal = self._localized_goal(language, structured.get("目标", "转化"))
        selling_points = self._localized_points(language, product.get("selling_points") or "真实卖点")
        campaign_rules = self._localized_rules(language, product.get("campaign_rules") or "以落地页真实活动规则为准")
        benchmark_hint = self._localized_benchmark_hint(language)
        if benchmarks:
            benchmark_hint = benchmarks[0].get("可复用结构") or benchmark_hint

        if language == "pt-BR":
            return {
                "素材方向": f"Mostre o valor real de {product_name} em {scene}, com foco em {goal}.",
                "脚本": {
                    "10秒脚本": f"Abra com uma necessidade em {scene}, mostre a interface real de {product_name}, destaque {selling_points} e finalize com as regras da oferta.",
                    "15秒脚本": f"Nos 3 primeiros segundos, apresente a dúvida do usuário. Depois, mostre logo e interface reais de {product_name}, explique {selling_points} e cite a regra: {campaign_rules}.",
                    "30秒脚本": f"Conte a jornada em cinco partes: contexto, uso do produto, benefício, regra da campanha e CTA. Use apenas fatos confirmados sobre {product_name}.",
                },
                "旁白": f"Confira {product_name} com atenção às regras reais, à interface do produto e ao que faz sentido para o seu uso.",
                "字幕": [
                    f"{scene}: confira as regras reais",
                    f"{product_name}: {selling_points}",
                    "A campanha segue as regras da página",
                    "Comece conferindo os detalhes",
                ],
                "分镜": [
                    {"镜头": 1, "画面": scene, "目的": "Apresentar contexto e necessidade"},
                    {"镜头": 2, "画面": "Logo e interface reais", "目的": "Construir confiança"},
                    {"镜头": 3, "画面": selling_points, "目的": "Explicar o valor principal"},
                    {"镜头": 4, "画面": campaign_rules, "目的": "Mostrar limites da oferta"},
                    {"镜头": 5, "画面": "CTA ou página de destino", "目的": "Conduzir a ação"},
                ],
                "Runway Prompt": f"Brazilian Portuguese ad video, real mobile usage scene, show {product_name} interface, clear pacing, no exaggerated claims.",
                "HeyGen Prompt": f"Brazilian Portuguese spokesperson video, calm and credible tone, explain {product_name}: {selling_points}, remind users to check page rules.",
                "ElevenLabs Prompt": "Brazilian Portuguese voiceover, natural rhythm, credible, clear, not exaggerated, suitable for performance ads.",
                "Facebook广告文案": f"Confira {product_name}: {selling_points}. Veja a interface real e as regras antes de participar. Comece pelos detalhes.",
                "TikTok广告文案": f"Veja como {product_name} funciona em {scene}. Regras claras, interface real e próximo passo simples. {benchmark_hint}",
                "合规提醒": "Use only confirmed product facts and real campaign rules.",
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
                "字幕": [
                    f"{scene}: consulta las reglas reales",
                    f"{product_name}: {selling_points}",
                    "La campaña sigue las reglas de la página",
                    "Comienza revisando los detalles",
                ],
                "分镜": [
                    {"镜头": 1, "画面": scene, "目的": "Presentar contexto y necesidad"},
                    {"镜头": 2, "画面": "Logo e interfaz reales", "目的": "Construir confianza"},
                    {"镜头": 3, "画面": selling_points, "目的": "Explicar el valor principal"},
                    {"镜头": 4, "画面": campaign_rules, "目的": "Mostrar límites de la oferta"},
                    {"镜头": 5, "画面": "CTA o landing page", "目的": "Guiar la acción"},
                ],
                "Runway Prompt": f"Spanish ad video, real mobile usage scene, show {product_name} interface, clear pacing, no exaggerated claims.",
                "HeyGen Prompt": f"Spanish spokesperson video, credible calm tone, explain {product_name}: {selling_points}, remind users to check page rules.",
                "ElevenLabs Prompt": "Spanish voiceover, natural rhythm, credible, clear, not exaggerated, suitable for performance ads.",
                "Facebook广告文案": f"Consulta {product_name}: {selling_points}. Revisa la interfaz real y las reglas antes de participar. Comienza por los detalles.",
                "TikTok广告文案": f"Así puedes revisar {product_name} en {scene}: reglas claras, interfaz real y próximo paso simple. Comienza por los detalles. {benchmark_hint}",
                "合规提醒": "Usa solo hechos confirmados del producto y reglas reales de campaña.",
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
                "字幕": [
                    f"{scene}: check the real rules",
                    f"{product_name}: {selling_points}",
                    "Campaign terms follow the landing page",
                    "Get started by checking the details",
                ],
                "分镜": [
                    {"镜头": 1, "画面": scene, "目的": "Set context and user need"},
                    {"镜头": 2, "画面": "Real logo and interface", "目的": "Build trust"},
                    {"镜头": 3, "画面": selling_points, "目的": "Explain the core value"},
                    {"镜头": 4, "画面": campaign_rules, "目的": "Show campaign boundaries"},
                    {"镜头": 5, "画面": "CTA or landing page", "目的": "Guide action"},
                ],
                "Runway Prompt": f"English ad video, real mobile usage scene, show {product_name} interface, clear pacing, no exaggerated claims.",
                "HeyGen Prompt": f"English spokesperson video, calm credible tone, explain {product_name}: {selling_points}, remind users to check page rules.",
                "ElevenLabs Prompt": "English voiceover, natural rhythm, credible, clear, not exaggerated, suitable for performance ads. Get started with a confident but restrained tone.",
                "Facebook广告文案": f"Check {product_name}: {selling_points}. Review the real interface and rules before joining. Get started with the details.",
                "TikTok广告文案": f"See how {product_name} works in {scene}: clear rules, real interface, simple next step. {benchmark_hint}",
                "合规提醒": "Use only confirmed product facts and real campaign rules.",
            }

        return {
            "素材方向": f"围绕{scene}展示{product_name}的真实使用价值，目标是{goal}。",
            "脚本": {
                "10秒脚本": f"开场点出{scene}的需求，展示{product_name}真实界面，强调{selling_points}，结尾提示查看活动规则。",
                "15秒脚本": f"前3秒提出用户困扰，中段用真实logo和界面展示{product_name}，说明{selling_points}，最后引用活动规则：{campaign_rules}。",
                "30秒脚本": f"用生活场景切入，拆成痛点、产品操作、卖点解释、活动规则、CTA五段；全程只表达{product_name}已确认事实，不做夸大承诺。",
            },
            "旁白": f"如果你也在{scene}需要更清晰的选择，可以看看{product_name}。重点看真实界面、真实规则和适合自己的操作路径。",
            "字幕": [
                f"{scene}，先看真实规则",
                f"{product_name}：{selling_points}",
                "活动以页面展示为准",
                "现在查看详情",
            ],
            "分镜": [
                {"镜头": 1, "画面": scene, "目的": "建立人群和问题"},
                {"镜头": 2, "画面": "展示真实logo和产品界面", "目的": "建立真实性"},
                {"镜头": 3, "画面": selling_points, "目的": "解释核心卖点"},
                {"镜头": 4, "画面": campaign_rules, "目的": "交代活动边界"},
                {"镜头": 5, "画面": "CTA按钮或落地页入口", "目的": "引导行动"},
            ],
            "Runway Prompt": f"中文广告短视频，真实手机使用场景，展示{product_name}界面，不虚构收益，节奏清晰，画面干净。",
            "HeyGen Prompt": f"中文口播，语气可信克制，说明{product_name}的真实卖点：{selling_points}，提醒活动以页面规则为准。",
            "ElevenLabs Prompt": "中文普通话旁白，节奏自然，可信、清晰、不夸张，适合投流素材。",
            "Facebook广告文案": f"{product_name}适合关注{goal}的用户。先看真实界面和活动规则，再决定是否参与。",
            "TikTok广告文案": f"{scene}可以这样看{product_name}：真实界面、真实规则、重点清楚。{benchmark_hint}",
            "合规提醒": audit.get("summary", "生成前需完成素材评估。"),
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
        return scene

    def _localized_goal(self, language, goal):
        if goal in ("注册转化", "转化"):
            return {
                "pt-BR": "cadastro",
                "es": "registro",
                "en": "signup",
                "zh": goal,
            }[language]
        return goal

    def _localized_points(self, language, points):
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
        return points

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
            return {"status": "BLOCKED", "阻断原因": audit.get("risks") or audit.get("missing_materials", [])}
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
                "素材方向",
                "脚本",
                "旁白",
                "字幕",
                "分镜",
                "Runway Prompt",
                "HeyGen Prompt",
                "ElevenLabs Prompt",
                "Facebook广告文案",
                "TikTok广告文案",
                "合规提醒",
            ],
            "script_required_fields": ["10秒脚本", "15秒脚本", "30秒脚本"],
        }
        result = self._request_json(
            "你是海外广告素材生成助手。输出必须是 JSON。字段名可用中文；正式素材内容必须按 language 输出；后台合规提醒可以中文。",
            payload,
        )
        self._require_keys(
            result,
            ("素材方向", "脚本", "旁白", "字幕", "分镜", "Runway Prompt", "HeyGen Prompt", "ElevenLabs Prompt", "Facebook广告文案", "TikTok广告文案", "合规提醒"),
            "素材内容",
        )
        self._require_keys(result["脚本"], ("10秒脚本", "15秒脚本", "30秒脚本"), "脚本")
        return result

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
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            response_format={"type": "json_object"},
        )
        text = self._response_text(response)
        return self._parse_json(text)

    def _response_text(self, response):
        if isinstance(response, str):
            return response
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text
        try:
            return response.output[0].content[0].text
        except (AttributeError, IndexError, TypeError) as exc:
            raise ProviderResponseError("OpenAI response did not contain readable JSON text.") from exc

    def _parse_json(self, text):
        candidate = (text or "").strip()
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

    def _language_instruction(self, language):
        normalized = self._normalize_language(language)
        return {
            "pt-BR": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用巴西葡萄牙语。",
            "es": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用西班牙语。",
            "en": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用英语。",
            "zh": "正式广告脚本、字幕、旁白、广告文案、视频 Prompt 必须使用中文。",
        }[normalized]
