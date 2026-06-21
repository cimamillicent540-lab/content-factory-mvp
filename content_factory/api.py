import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from content_factory.config import load_settings
from content_factory.db import connect, init_db
from content_factory.provider_factory import create_provider
from content_factory.services import (
    get_generation_result,
    record_performance_feedback,
    run_content_pipeline,
)


JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}
HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


class ContentFactoryAPI:
    def __init__(self, database_path):
        self.conn = connect(database_path)
        init_db(self.conn)
        self.provider = create_provider()

    def handle(self, method, path, payload=None):
        if method == "GET" and path == "/":
            return 200, dict(HTML_HEADERS), _homepage_html()

        if method == "GET" and path == "/health":
            return self._json(200, {"status": "ok", "message": "内容工厂 API 正常"})

        if method == "POST" and path == "/generate":
            return self._handle_generate(payload or {})

        generation_match = re.fullmatch(r"/generations/(\d+)", path)
        if method == "GET" and generation_match:
            return self._handle_get_generation(int(generation_match.group(1)))

        feedback_match = re.fullmatch(r"/generations/(\d+)/feedback", path)
        if method == "POST" and feedback_match:
            return self._handle_feedback(int(feedback_match.group(1)), payload or {})

        return self._json(404, {"status": "NOT_FOUND", "message": "接口不存在"})

    def _handle_generate(self, payload):
        result = run_content_pipeline(self.conn, self.provider, payload)
        if result["状态"] == "BLOCKED":
            return self._json(
                409,
                {
                    "status": "BLOCKED",
                    "generation_id": None,
                    "结构化需求": _load_demand(self.conn, result["demand_id"]),
                    "红线审核结果": result["素材审核"],
                    "阻断原因": result["阻断原因"],
                },
            )

        performance = record_performance_feedback(
            self.conn,
            self.provider,
            result["generation_id"],
            payload.get("投放数据", _default_performance_metrics()),
        )
        saved = get_generation_result(self.conn, result["generation_id"])
        return self._json(
            200,
            {
                "status": "GENERATED",
                "generation_id": result["generation_id"],
                "结构化需求": saved["demand"]["structured"],
                "红线审核结果": saved["audit"],
                "素材内容": saved["generation"],
                "100分评分报告": saved["evaluation"],
                "投放分析建议": performance["投放分析建议"],
            },
        )

    def _handle_get_generation(self, generation_id):
        saved = get_generation_result(self.conn, generation_id)
        if saved is None:
            return self._json(404, {"status": "NOT_FOUND", "message": "生成记录不存在"})
        return self._json(
            200,
            {
                "status": "FOUND",
                "generation_id": generation_id,
                "结构化需求": saved["demand"]["structured"],
                "红线审核结果": saved["audit"],
                "素材内容": saved["generation"],
                "100分评分报告": saved["evaluation"],
                "投放记录": saved["performance_logs"],
            },
        )

    def _handle_feedback(self, generation_id, payload):
        try:
            feedback = record_performance_feedback(self.conn, self.provider, generation_id, payload)
        except ValueError:
            return self._json(404, {"status": "NOT_FOUND", "message": "生成记录不存在"})
        return self._json(
            200,
            {
                "status": "RECORDED",
                "generation_id": generation_id,
                "投放分析建议": feedback["投放分析建议"],
            },
        )

    def _json(self, status, payload):
        return status, dict(JSON_HEADERS), json.dumps(payload, ensure_ascii=False, indent=2)


def create_app(database_path=None):
    settings = load_settings()
    return ContentFactoryAPI(database_path or settings.database_path)


def run_server(database_path=None, host=None, port=None):
    settings = load_settings()
    app = create_app(database_path or settings.database_path)
    server_host = host or settings.host
    server_port = port or settings.port

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def _dispatch(self, method):
            payload = self._read_json() if method == "POST" else None
            status, headers, body = app.handle(method, self.path, payload)
            encoded = body.encode("utf-8")
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)

    server = ThreadingHTTPServer((server_host, server_port), Handler)
    print(f"内容工厂 API 已启动：http://{server_host}:{server_port}")
    server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description="海外投流素材内容工厂 HTTP API")
    parser.add_argument("--database-path", default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    run_server(args.database_path, args.host, args.port)


def _load_demand(conn, demand_id):
    row = conn.execute("SELECT structured_json FROM demand_intakes WHERE id = ?", (demand_id,)).fetchone()
    return json.loads(row["structured_json"]) if row else {}


def _default_performance_metrics():
    return {"ctr": 0.8, "cpa": 20, "play_3s": 1000, "play_50": 300}


def _homepage_html():
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Content Factory MVP</title>
  <style>
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7fb;
      color: #172033;
      --line: #dde3ef;
      --soft: #f8fafc;
      --blue: #155eef;
      --red: #b42318;
      --green: #027a48;
    }
    body { margin: 0; }
    main { max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }
    h1 { font-size: 28px; margin: 0 0 6px; }
    h2 { margin: 0 0 14px; font-size: 21px; }
    h3 { margin: 0 0 10px; font-size: 16px; }
    p { margin: 0 0 20px; color: #586176; }
    form {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      background: #fff;
      border: 1px solid #dde3ef;
      border-radius: 8px;
      padding: 18px;
    }
    label { display: grid; gap: 6px; font-size: 14px; font-weight: 650; }
    input, textarea, button {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 10px 11px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 84px; resize: vertical; }
    .wide { grid-column: 1 / -1; }
    button {
      width: max-content;
      border-color: var(--blue);
      border-radius: 6px;
      padding: 10px 16px;
      background: var(--blue);
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    pre {
      margin-top: 18px;
      padding: 18px;
      min-height: 220px;
      overflow: auto;
      border-radius: 8px;
      border: 1px solid #dde3ef;
      background: #101828;
      color: #e6edf7;
      white-space: pre-wrap;
    }
    #output { margin-top: 18px; }
    .status { margin-top: 14px; font-weight: 700; }
    .blocked { color: var(--red); }
    .generated { color: var(--green); }
    .section {
      margin-top: 18px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    .field { padding: 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--soft); }
    .field b { display: block; margin-bottom: 5px; color: #586176; font-size: 12px; }
    .creative-card { margin-top: 12px; padding: 14px; border: 2px solid #c7d7fe; border-radius: 8px; background: #fbfcff; }
    .creative-card header { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
    .pill { border-radius: 999px; background: #e0eaff; color: #1849a9; padding: 4px 9px; font-weight: 800; font-size: 12px; }
    textarea.copy-box { min-height: 96px; margin: 8px 0 12px; background: #101828; color: #e6edf7; border-color: #101828; }
    .danger { border-color: #f2b8b5; background: #fff7f6; }
    ul { margin: 8px 0 0; padding-left: 20px; }
    details { margin-top: 18px; }
    summary { cursor: pointer; font-weight: 800; }
    @media (max-width: 760px) {
      form { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <main>
    <h1>Content Factory MVP</h1>
    <p>Overseas Ad Creative Generator</p>
    <p hidden>海外投流素材内容工厂</p>
    <form id="factory-form">
      <label>行业 industry
        <input name="industry" value="crypto exchange" required>
      </label>
      <label>产品 product
        <input name="product" value="Spikex" required>
      </label>
      <label>平台 platform
        <input name="platform" value="Facebook Ads" required>
      </label>
      <label>国家 country
        <input name="country" value="Brazil" required>
      </label>
      <label>语言 language
        <input name="language" value="Brazilian Portuguese" required>
      </label>
      <label>人群 audience
        <input name="audience" value="Brazilian retail traders interested in crypto, stocks, copy trading and AI trading tools" required>
      </label>
      <label class="wide">卖点 selling_points
        <input name="selling_points" value="AI copy trading, crypto trading, US stocks trading, fast onboarding, beginner-friendly trading experience" required>
      </label>
      <label>时长 duration
        <input name="duration" value="15" required>
      </label>
      <label>活动规则 campaign_rules
        <input name="campaign_rules" value="Avoid unrealistic financial promises, avoid exaggerated claims, follow platform ad policy, include risk-aware language">
      </label>
      <label>禁用表达 forbidden_claims
        <input name="forbidden_claims" value="guaranteed profit, risk-free, no loss">
      </label>
      <label>限制词/红线词 restrictions
        <input name="restrictions" value="guaranteed profit, risk-free, no loss" required>
      </label>
      <label class="wide">自定义需求 demand
        <textarea name="demand" placeholder="留空则根据字段自动生成需求">Generate 5 short video ad concepts with hooks, scripts, voiceover, captions and Runway prompts</textarea>
      </label>
      <div class="wide">
        <button type="submit">生成素材卡片</button>
      </div>
    </form>
    <div id="status" class="status">等待生成</div>
    <div id="output">生成结果会显示在这里。</div>
  </main>
  <script>
    const form = document.getElementById('factory-form');
    const statusBox = document.getElementById('status');
    const output = document.getElementById('output');
    const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
    const field = (label, value) => `<div class="field"><b>${escapeHtml(label)}</b><div>${escapeHtml(value || '')}</div></div>`;
    const list = (items) => Array.isArray(items) ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : `<p>${escapeHtml(items || '')}</p>`;
    const copyBox = (value) => `<textarea class="copy-box" readonly>${escapeHtml(value || '')}</textarea>`;

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      statusBox.className = 'status';
      statusBox.textContent = '生成中...';
      const payload = {
        "行业": form.industry.value,
        "产品": form.product.value,
        "投放平台": form.platform.value,
        "国家": form.country.value,
        "语言": form.language.value,
        "目标人群": form.audience.value,
        "卖点": form.selling_points.value,
        "活动规则": form.campaign_rules.value,
        "限制词": form.forbidden_claims.value || form.restrictions.value,
        // legacy payload shape: "限制词": form.restrictions.value
        "需求": form.demand.value || `给${form.platform.value}${form.country.value}${form.audience.value}做一条${form.duration.value}注册转化素材`,
        "素材": [
          {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
          {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
          {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1}
        ]
      };

      const response = await fetch('/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (result.status === 'BLOCKED') {
        renderBlocked(result);
      } else {
        renderGenerated(result);
      }
    });

    function renderGenerated(result) {
      const content = result["素材内容"] || {};
      const summary = content.campaign_summary || {};
      const concepts = content.video_ad_concepts || [];
      statusBox.className = 'status generated';
      statusBox.textContent = `GENERATED generation_id=${result.generation_id} 素材内容`;
      output.innerHTML = `
        <section class="section">${renderStatus(result, summary)}</section>
        <section class="section"><h2>5 套素材卡片</h2>${concepts.map(renderCreativeCard).join('')}</section>
        <section class="section"><h2>Prompt 专区</h2>${concepts.map(renderPromptBlock).join('')}</section>
        <section class="section"><h2>Facebook Ads 文案专区</h2>${concepts.map(renderFacebookBlock).join('')}</section>
        <section class="section"><h2>评分报告区 scoring_report</h2>${renderScoring(content.scoring_report || {})}</section>
        <section class="section"><h2>制作建议区</h2>${renderKeyValues(content.media_production_notes || {})}</section>
        <section class="section"><h2>投放计划区 launch_plan</h2>${renderLaunchPlan(content.launch_plan || {})}</section>
        <section class="section"><h2>红线检查区 forbidden_claims_check</h2>${renderForbiddenCheck(content.forbidden_claims_check || {})}</section>
        ${renderRawJson(result)}
      `;
    }

    function renderStatus(result, summary) {
      return `<h2>顶部状态区</h2><div class="grid">
        ${field('状态', 'GENERATED')}
        ${field('generation_id', result.generation_id)}
        ${field('产品', summary["产品"])}
        ${field('国家', summary["国家"])}
        ${field('平台', summary["平台"])}
        ${field('投放语言', summary["投放语言"])}
        ${field('目标人群', summary["目标人群"])}
        ${field('核心卖点', summary["核心卖点"])}
        ${field('风险提醒', summary["风险提醒"])}
      </div>`;
    }

    function renderCreativeCard(concept) {
      return `<article class="creative-card">
        <header><h3>${escapeHtml(concept.concept_name)}</h3><span class="pill">${escapeHtml(concept.concept_id)}</span></header>
        <div class="grid">
          ${field('target_angle', concept.target_angle)}
          ${field('hook', concept.hook)}
          ${field('15s_script', concept["15s_script"])}
          ${field('voiceover', concept.voiceover)}
          ${field('captions', Array.isArray(concept.captions) ? concept.captions.join(' / ') : concept.captions)}
          ${field('runway_prompt', concept.runway_prompt)}
          ${field('elevenlabs_prompt', concept.elevenlabs_prompt)}
          ${field('facebook_primary_text', concept.facebook_primary_text)}
          ${field('facebook_headline', concept.facebook_headline)}
          ${field('facebook_description', concept.facebook_description)}
        </div>
      </article>`;
    }

    function renderPromptBlock(concept) {
      return `<article class="creative-card"><header><h3>${escapeHtml(concept.concept_id)} Prompt</h3></header>
        <b>Runway Prompt</b>${copyBox(concept.runway_prompt)}
        <b>ElevenLabs Prompt</b>${copyBox(concept.elevenlabs_prompt)}
      </article>`;
    }

    function renderFacebookBlock(concept) {
      return `<article class="creative-card"><header><h3>${escapeHtml(concept.concept_id)} Facebook Ads</h3></header>
        <div class="grid">
          ${field('Primary Text', concept.facebook_primary_text)}
          ${field('Headline', concept.facebook_headline)}
          ${field('Description', concept.facebook_description)}
        </div>
      </article>`;
    }

    function renderScoring(report) {
      return `<div class="grid">
        ${field('hook_score', report.hook_score)}
        ${field('clarity_score', report.clarity_score)}
        ${field('trust_score', report.trust_score)}
        ${field('compliance_score', report.compliance_score)}
        ${field('localization_score', report.localization_score)}
        ${field('conversion_potential_score', report.conversion_potential_score)}
        ${field('total_score', report.total_score)}
      </div><h3>improvement_suggestions</h3>${list(report.improvement_suggestions || [])}`;
    }

    function renderKeyValues(value) {
      return `<div class="grid">${Object.entries(value).map(([key, item]) => field(key, Array.isArray(item) ? item.join('，') : item)).join('')}</div>`;
    }

    function renderLaunchPlan(plan) {
      return `<div class="grid">
        ${field('推荐优先测试', Array.isArray(plan["推荐优先测试"]) ? plan["推荐优先测试"].join('，') : plan["推荐优先测试"])}
        ${field('为什么先测', plan["为什么先测"])}
        ${field('初始投放观察指标', Array.isArray(plan["初始投放观察指标"]) ? plan["初始投放观察指标"].join('，') : plan["初始投放观察指标"])}
      </div><h3>每套适合的受众角度</h3>${renderKeyValues(plan["每套适合的受众角度"] || {})}`;
    }

    function renderForbiddenCheck(check) {
      return `<div class="grid">
        ${field('是否命中禁用词', check["是否命中禁用词"])}
        ${field('命中的词', Array.isArray(check["命中的词"]) ? check["命中的词"].join('，') : check["命中的词"])}
        ${field('风险说明', check["风险说明"])}
        ${field('替代表达建议', Array.isArray(check["替代表达建议"]) ? check["替代表达建议"].join('；') : check["替代表达建议"])}
      </div>`;
    }

    function renderBlocked(result) {
      const audit = result["红线审核结果"] || {};
      statusBox.className = 'status blocked';
      statusBox.textContent = `BLOCKED：${(result["阻断原因"] || []).join('，')}`;
      output.innerHTML = `<section class="section danger">
        <h2>BLOCKED</h2>
        <p>BLOCKED 状态不展示素材卡片</p>
        <div class="grid">
          ${field('阻断原因', (result["阻断原因"] || []).join('，'))}
          ${field('summary', audit.summary)}
          ${field('risks', (audit.risks || []).join('，'))}
          ${field('risk_explanation', audit.risk_explanation)}
          ${field('替代表达建议', (audit["替代表达建议"] || []).join('；'))}
          ${field('next_actions', (audit.next_actions || []).join('，'))}
          ${field('结构化需求', JSON.stringify(result["结构化需求"] || {}, null, 2))}
        </div>
      </section>${renderRawJson(result)}`;
    }

    function renderRawJson(result) {
      return `<details><summary>查看原始 JSON</summary><pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre></details>`;
    }
  </script>
</body>
</html>"""


if __name__ == "__main__":
    main()
