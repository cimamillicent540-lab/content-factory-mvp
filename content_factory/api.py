import argparse
import html
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from content_factory.config import load_settings
from content_factory.creative_workflow import attach_creative_ids, build_media_buyer_launch_brief
from content_factory.db import connect, init_db, loads_json
from content_factory.next_round_recommendations import (
    build_next_round_recommendations,
    next_round_plan_markdown,
)
from content_factory.next_round_brief_request import build_next_round_brief_request
from content_factory.performance_reports import (
    get_performance_report,
    list_performance_reports,
    save_performance_report,
)
from content_factory.product_profiles import list_product_profiles, profile_to_generation_request
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

        if method == "GET" and path == "/performance":
            return 200, dict(HTML_HEADERS), _performance_html()

        if method == "POST" and path == "/performance":
            return self._handle_performance(payload or {})

        if method == "GET" and path == "/performance/history":
            return self._handle_performance_history()

        performance_match = re.fullmatch(r"/performance/history/(perf-[A-Za-z0-9-]+)", path)
        if method == "GET" and performance_match:
            return self._handle_performance_report_detail(performance_match.group(1))

        if method == "GET" and path == "/history":
            return self._handle_history()

        history_match = re.fullmatch(r"/history/(\d+|blocked-\d+)", path)
        if method == "GET" and history_match:
            return self._handle_history_detail(history_match.group(1))

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
                "profile_id": saved["product"].get("profile_id", ""),
                "product_facts": saved["product"].get("product_facts", []),
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

    def _handle_performance(self, payload):
        csv_text = payload.get("csv") or payload.get("csv_text") or ""
        report = save_performance_report(self.conn, csv_text)
        return 200, dict(HTML_HEADERS), _performance_html(csv_text, report["aggregated"], report["summary"], report)

    def _handle_performance_history(self):
        reports = list_performance_reports(self.conn)
        return 200, dict(HTML_HEADERS), _performance_history_html(reports)

    def _handle_performance_report_detail(self, report_id):
        report = get_performance_report(self.conn, report_id)
        if report is None:
            return 404, dict(HTML_HEADERS), _performance_report_not_found_html(report_id)
        return 200, dict(HTML_HEADERS), _performance_report_detail_html(report)

    def _handle_history(self):
        rows = self.conn.execute(
            """
            SELECT
                ma.id AS audit_id,
                ma.status AS audit_status,
                ma.created_at AS audit_created_at,
                cg.id AS generation_id,
                cg.created_at AS generation_created_at,
                cg.generation_json AS generation_json,
                p.name AS product,
                p.category AS industry,
                p.platform AS platform,
                p.country AS country,
                di.structured_json AS structured_json
            FROM material_audits ma
            JOIN products p ON p.id = ma.product_id
            JOIN demand_intakes di ON di.id = ma.demand_id
            LEFT JOIN content_generations cg ON cg.audit_id = ma.id
            ORDER BY ma.id DESC
            LIMIT 50
            """
        ).fetchall()
        return 200, dict(HTML_HEADERS), _history_html(rows)

    def _handle_history_detail(self, history_id):
        if history_id.startswith("blocked-"):
            audit_id = int(history_id.replace("blocked-", "", 1))
            row = self.conn.execute(
                """
                SELECT
                    ma.id AS audit_id,
                    ma.status AS audit_status,
                    ma.audit_json AS audit_json,
                    ma.created_at AS created_at,
                    p.name AS product,
                    p.category AS industry,
                    p.platform AS platform,
                    p.country AS country,
                    di.raw_input AS raw_input,
                    di.structured_json AS structured_json
                FROM material_audits ma
                JOIN products p ON p.id = ma.product_id
                JOIN demand_intakes di ON di.id = ma.demand_id
                LEFT JOIN content_generations cg ON cg.audit_id = ma.id
                WHERE ma.id = ? AND cg.id IS NULL
                """,
                (audit_id,),
            ).fetchone()
            if row is None:
                return 404, dict(HTML_HEADERS), _history_not_found_html(history_id)
            return 200, dict(HTML_HEADERS), _blocked_history_detail_html(row)

        generation_id = int(history_id)
        saved = get_generation_result(self.conn, generation_id)
        if saved is None:
            return 404, dict(HTML_HEADERS), _history_not_found_html(history_id)
        generation_row = self.conn.execute("SELECT created_at FROM content_generations WHERE id = ?", (generation_id,)).fetchone()
        return 200, dict(HTML_HEADERS), _generated_history_detail_html(generation_id, saved, generation_row["created_at"] if generation_row else "")

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


def _escape(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _format_brief_value(value):
    if isinstance(value, list):
        return " / ".join(str(item) for item in value)
    if isinstance(value, dict):
        return " / ".join(f"{key}: {_format_brief_value(item)}" for key, item in value.items())
    return str(value if value is not None else "")


def _brief_line(label, value):
    if value in (None, ""):
        return None
    if isinstance(value, (list, dict)) and not value:
        return None
    return f"- {label}: {_format_brief_value(value)}"


def _creative_brief_markdown(saved, generation_id, created_at=None):
    product = saved.get("product", {})
    demand = saved.get("demand", {}).get("structured", {})
    generation = saved.get("generation", {})
    summary = generation.get("campaign_summary", {})
    concepts = attach_creative_ids(
        generation.get("video_ad_concepts", []),
        product.get("name"),
        summary.get("国家") or product.get("country"),
        summary.get("平台") or product.get("platform"),
        created_at,
    )
    report = generation.get("scoring_report", {})
    notes = generation.get("media_production_notes", {})
    launch_plan = generation.get("launch_plan", {})
    forbidden_check = generation.get("forbidden_claims_check", {})
    lines = ["# Creative Brief", "", "## Campaign Summary"]
    for line in (
        _brief_line("generation_id", generation_id),
        _brief_line("product", summary.get("产品") or product.get("name")),
        _brief_line("industry", product.get("category")),
        _brief_line("platform", summary.get("平台") or product.get("platform")),
        _brief_line("country", summary.get("国家") or product.get("country")),
        _brief_line("language", summary.get("投放语言") or demand.get("语言")),
        _brief_line("audience", summary.get("目标人群") or demand.get("人群")),
        _brief_line("selling points", summary.get("核心卖点") or product.get("selling_points")),
        _brief_line("campaign rules summary", product.get("campaign_rules")),
    ):
        if line:
            lines.append(line)
    product_facts = product.get("product_facts", [])
    if product_facts:
        lines.extend(["", "### Product Facts"])
        lines.extend(f"- {fact}" for fact in product_facts)

    lines.extend(["", "## Creative Concepts"])
    for concept in concepts:
        lines.extend(["", f"### {_format_brief_value(concept.get('concept_id'))} {_format_brief_value(concept.get('concept_name'))}".strip()])
        line = _brief_line("Creative ID", concept.get("creative_id"))
        if line:
            lines.append(line)
        for key in (
            "creative_id",
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
        ):
            line = _brief_line(key, concept.get(key))
            if line:
                lines.append(line)

    lines.extend(["", "## Scoring Report"])
    for key in (
        "total_score",
        "hook_score",
        "clarity_score",
        "compliance_score",
        "localization_score",
        "conversion_potential_score",
        "improvement_suggestions",
    ):
        line = _brief_line(key, report.get(key))
        if line:
            lines.append(line)

    lines.extend(["", "## Media Production Notes"])
    for key, value in notes.items():
        line = _brief_line(key, value)
        if line:
            lines.append(line)

    lines.extend(["", "## Launch Plan"])
    for key, value in launch_plan.items():
        line = _brief_line(key, value)
        if line:
            lines.append(line)

    lines.extend(["", "## Forbidden Claims Check"])
    for key, value in forbidden_check.items():
        line = _brief_line(key, value)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _history_html(rows):
    cards = []
    for row in rows:
        structured = loads_json(row["structured_json"], {})
        generation = loads_json(row["generation_json"], {}) if row["generation_json"] else {}
        status = "GENERATED" if row["generation_id"] else "BLOCKED"
        history_id = str(row["generation_id"]) if row["generation_id"] else f"blocked-{row['audit_id']}"
        concept_count = len(generation.get("video_ad_concepts", [])) if generation else 0
        cards.append(
            f"""
            <article class="history-card">
              <h2>{_escape(status)} #{_escape(history_id)}</h2>
              <p>generation_id: {_escape(history_id)}</p>
              <p>status: {_escape(status)}</p>
              <p>created_at: {_escape(row["generation_created_at"] or row["audit_created_at"])}</p>
              <p>industry: {_escape(row["industry"])}</p>
              <p>product: {_escape(row["product"])}</p>
              <p>platform: {_escape(row["platform"])}</p>
              <p>country: {_escape(row["country"])}</p>
              <p>language: {_escape(structured.get("语言", ""))}</p>
              <p>concept count: {_escape(concept_count)}</p>
              <p>is BLOCKED: {_escape(status == "BLOCKED")}</p>
              <a href="/history/{_escape(history_id)}">View</a>
            </article>
            """
        )
    body = "\n".join(cards) or "<p>No generation history yet.</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Generation History</title>{_history_style()}</head>
<body><main>
  <nav><a href="/">Back to Generator</a></nav>
  <h1>Generation History</h1>
  <p>Recent local saved briefs and blocked generation attempts.</p>
  {body}
</main></body></html>"""


def _generated_history_detail_html(generation_id, saved, created_at):
    brief = _creative_brief_markdown(saved, generation_id, created_at)
    generation = saved.get("generation", {})
    product = saved.get("product", {})
    summary = generation.get("campaign_summary", {})
    concepts = attach_creative_ids(
        generation.get("video_ad_concepts", []),
        product.get("name"),
        summary.get("国家") or product.get("country"),
        summary.get("平台") or product.get("platform"),
        created_at,
    )
    launch_brief = build_media_buyer_launch_brief(
        {
            "product": summary.get("产品") or product.get("name"),
            "profile_id": product.get("profile_id", ""),
            "platform": summary.get("平台") or product.get("platform"),
            "country": summary.get("国家") or product.get("country"),
            "language": summary.get("投放语言") or saved.get("demand", {}).get("structured", {}).get("语言"),
            "audience": summary.get("目标人群") or saved.get("demand", {}).get("structured", {}).get("人群"),
            "campaign_rules": product.get("campaign_rules"),
        },
        concepts,
    )
    raw_payload = {
        "status": "GENERATED",
        "generation_id": generation_id,
        "created_at": created_at,
        "product": saved.get("product", {}),
        "product_facts": saved.get("product", {}).get("product_facts", []),
        "结构化需求": saved.get("demand", {}).get("structured", {}),
        "红线审核结果": saved.get("audit", {}),
        "素材内容": saved.get("generation", {}),
        "100分评分报告": saved.get("evaluation", {}),
        "投放记录": saved.get("performance_logs", []),
    }
    concept_cards = "\n".join(
        f"<article class=\"history-card\"><h3>{_escape(concept.get('concept_id'))} {_escape(concept.get('concept_name'))}</h3>"
        f"<p>Creative ID: {_escape(concept.get('creative_id'))}</p>"
        f"<p>hook: {_escape(concept.get('hook'))}</p>"
        f"<p>runway_prompt: {_escape(concept.get('runway_prompt'))}</p>"
        f"<p>elevenlabs_prompt: {_escape(concept.get('elevenlabs_prompt'))}</p></article>"
        for concept in concepts
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Generation Detail</title>{_history_style()}</head>
<body><main>
  <nav><a href="/history">Back to History</a></nav>
  <h1>Generation Detail</h1>
  <p>status: GENERATED</p>
  <p>generation_id: {_escape(generation_id)}</p>
  <p>created_at: {_escape(created_at)}</p>
  <section><h2>Creative Brief Markdown</h2><button type="button" onclick="copyFullBrief()">Copy Full Brief</button><textarea id="creative-brief-markdown" class="brief-copy-box" readonly>{_escape(brief)}</textarea></section>
  <section><h2>Media Buyer Launch Brief</h2><button type="button" onclick="copyLaunchBrief()">Copy Launch Brief</button><textarea id="media-buyer-launch-brief" class="brief-copy-box launch-brief-copy-box" readonly>{_escape(launch_brief)}</textarea></section>
  <section><h2>Creative Concepts</h2>{concept_cards}</section>
  <section><h2>Raw JSON</h2><pre>{_escape(json.dumps(raw_payload, ensure_ascii=False, indent=2))}</pre></section>
  <script>{_copy_script()}</script>
</main></body></html>"""


def _blocked_history_detail_html(row):
    audit = loads_json(row["audit_json"], {})
    structured = loads_json(row["structured_json"], {})
    risks = audit.get("risks") or audit.get("missing_materials") or []
    raw_payload = {
        "status": "BLOCKED",
        "generation_id": f"blocked-{row['audit_id']}",
        "created_at": row["created_at"],
        "product": {
            "name": row["product"],
            "category": row["industry"],
            "platform": row["platform"],
            "country": row["country"],
        },
        "结构化需求": structured,
        "红线审核结果": audit,
        "阻断原因": risks,
    }
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Generation Detail</title>{_history_style()}</head>
<body><main>
  <nav><a href="/history">Back to History</a></nav>
  <h1>Generation Detail</h1>
  <section class="danger">
    <h2>BLOCKED</h2>
    <p>阻断原因: {_escape(", ".join(str(item) for item in risks))}</p>
    <p>risks: {_escape(", ".join(str(item) for item in audit.get("risks", [])))}</p>
    <p>risk_explanation: {_escape(audit.get("risk_explanation") or audit.get("summary", ""))}</p>
    <p>safer_alternatives: {_escape(_format_brief_value(audit.get("替代表达建议", [])))}</p>
    <p>next_actions: {_escape(_format_brief_value(audit.get("next_actions", [])))}</p>
  </section>
  <section><h2>Raw JSON</h2><pre>{_escape(json.dumps(raw_payload, ensure_ascii=False, indent=2))}</pre></section>
</main></body></html>"""


def _history_not_found_html(history_id):
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>History record not found</title>{_history_style()}</head>
<body><main><h1>History record not found</h1><p>No saved generation history for {_escape(history_id)}.</p><a href="/history">Back to History</a></main></body></html>"""


def _history_style():
    return """<style>
      body { margin: 0; background: #f5f7fb; color: #172033; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      main { max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }
      a { color: #155eef; font-weight: 700; }
      .history-card, section { margin-top: 16px; padding: 16px; border: 1px solid #dde3ef; border-radius: 8px; background: #fff; }
      .danger { border-color: #f2b8b5; background: #fff7f6; }
      textarea.brief-copy-box { width: 100%; min-height: 420px; box-sizing: border-box; background: #101828; color: #e6edf7; border: 1px solid #101828; border-radius: 8px; padding: 14px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
      pre { overflow: auto; white-space: pre-wrap; background: #101828; color: #e6edf7; padding: 14px; border-radius: 8px; }
      button { border: 1px solid #155eef; border-radius: 6px; padding: 10px 16px; background: #155eef; color: #fff; font-weight: 700; cursor: pointer; }
    </style>"""


def _copy_script():
    return """
      async function copyFullBrief() {
        const target = document.getElementById('creative-brief-markdown');
        if (!target) return;
        target.select();
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(target.value);
        } else {
          document.execCommand('copy');
        }
      }
      async function copyLaunchBrief() {
        const target = document.getElementById('media-buyer-launch-brief');
        if (!target) return;
        target.select();
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(target.value);
        } else {
          document.execCommand('copy');
        }
      }
    """


def _sample_performance_csv():
    return """creative_id,spend,impressions,clicks,link_clicks,registrations,deposits,video_3s_views,video_50_views,video_95_views
SPK-BR-FB-20260628-C001,30,5000,80,65,5,1,1200,500,220
SPK-BR-FB-20260628-C002,25,4500,35,28,1,0,600,180,60
SPK-BR-FB-20260628-C003,20,3000,70,60,0,0,1000,650,300
"""


def _performance_html(csv_text=None, aggregated=None, summary=None, report=None):
    csv_value = csv_text if csv_text is not None else _sample_performance_csv()
    results = _performance_results_html(aggregated, summary, report) if aggregated is not None and summary is not None else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Performance CSV Analyzer</title>
  {_history_style()}
  <style>
    .performance-form {{ display: grid; gap: 12px; margin-top: 16px; }}
    .performance-form textarea {{ width: 100%; min-height: 220px; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border-bottom: 1px solid #dde3ef; padding: 9px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #f8fafc; }}
    .warning {{ border-color: #fed7aa; background: #fff7ed; }}
  </style>
</head>
<body><main>
  <nav><a href="/">Back to Generator</a> · <a href="/history">Generation History</a></nav>
  <h1>Performance CSV Analyzer</h1>
  <p>Paste media buying CSV data to match Creative IDs, calculate CTR / CPC / CPM / CPA / video retention, and produce internal next-step notes.</p>
  <section>
    <h2>Paste CSV</h2>
    <div class="performance-form">
      <textarea id="performance-csv" name="csv">{_escape(csv_value)}</textarea>
      <button type="button" onclick="analyzePerformance()">Analyze Performance</button>
    </div>
  </section>
  <section>
    <h2>Sample CSV</h2>
    <p>Use this sample to smoke test Creative ID matching and report saving.</p>
    <button type="button" onclick="copySampleCsv()">Copy Sample CSV</button>
    <textarea id="sample-performance-csv" class="brief-copy-box" readonly>{_escape(_sample_performance_csv())}</textarea>
  </section>
  <div id="performance-output">{results}</div>
  <script>
    async function analyzePerformance() {{
      const csv = document.getElementById('performance-csv').value;
      const response = await fetch('/performance', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{csv}})
      }});
      document.open();
      document.write(await response.text());
      document.close();
    }}
    async function copyPerformanceSummary() {{
      const target = document.getElementById('performance-summary-markdown');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(target.value);
      }} else {{
        document.execCommand('copy');
      }}
    }}
    async function copySampleCsv() {{
      const target = document.getElementById('sample-performance-csv');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(target.value);
      }} else {{
        document.execCommand('copy');
      }}
    }}
  </script>
</main></body></html>"""


def _performance_results_html(aggregated, summary, report=None):
    creatives = aggregated.get("creatives", {})
    rows = []
    for creative_id, metrics in creatives.items():
        rows.append(
            f"""<tr>
              <td>{_escape(creative_id)}</td>
              <td>{_escape(metrics.get("recommendation"))}</td>
              <td>{_escape(metrics.get("reason"))}</td>
              <td>{_format_money(metrics.get("total_spend"))}</td>
              <td>{_format_number(metrics.get("impressions"))}</td>
              <td>{_format_percent(metrics.get("ctr"))}</td>
              <td>{_format_percent(metrics.get("link_ctr"))}</td>
              <td>{_format_money(metrics.get("cpc"))}</td>
              <td>{_format_money(metrics.get("cpm"))}</td>
              <td>{_format_money(metrics.get("cpa_registration"))}</td>
              <td>{_format_money(metrics.get("cpa_deposit"))}</td>
              <td>{_format_percent(metrics.get("video_3s_rate"))}</td>
              <td>{_format_percent(metrics.get("video_50_retention"))}</td>
              <td>{_format_percent(metrics.get("video_95_retention"))}</td>
              <td>{_escape(metrics.get("action"))}</td>
            </tr>"""
        )
    table_rows = "\n".join(rows) or "<tr><td colspan=\"15\">No matched Creative ID found.</td></tr>"
    unmatched_html = ""
    if aggregated.get("unmatched_rows"):
        unmatched_html = f"""<section class="warning">
          <h2>Unmatched Rows</h2>
          <p>No Creative ID found in {len(aggregated.get("unmatched_rows", []))} row(s). Check creative_id, ad_name, campaign_name, or adset_name naming.</p>
          <pre>{_escape(json.dumps(aggregated.get("unmatched_rows", []), ensure_ascii=False, indent=2))}</pre>
        </section>"""
    summary_markdown = report.get("summary_markdown") if report else _performance_summary_markdown(summary, creatives)
    saved_notice = _performance_saved_notice(report) if report else ""
    return f"""
      {saved_notice}
      <section>
        <h2>Summary</h2>
        <div class="grid">
          {_kv_card("matched creatives", summary.get("total_creatives_matched"))}
          {_kv_card("unmatched rows", summary.get("missing_creative_id_rows_count"))}
          {_kv_card("total spend", _format_money(summary.get("total_spend")))}
          {_kv_card("best creative by CTR", _summary_best(summary.get("best_creative_by_ctr")))}
          {_kv_card("best creative by registrations", _summary_best(summary.get("best_creative_by_registrations")))}
          {_kv_card("best creative by deposits", _summary_best(summary.get("best_creative_by_deposits")))}
        </div>
      </section>
      <section>
        <h2>Creative Performance Table</h2>
        <table>
          <thead><tr>
            <th>Creative ID</th><th>recommendation</th><th>reason</th><th>Spend</th><th>Impressions</th><th>CTR</th><th>Link CTR</th><th>CPC</th><th>CPM</th><th>CPA registration</th><th>CPA deposit</th><th>3s rate</th><th>50% retention</th><th>95% retention</th><th>Internal Action Notes</th>
          </tr></thead>
          <tbody>{table_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>Internal Action Notes</h2>
        <ul>{"".join(f"<li>{_escape(note)}</li>" for note in summary.get("internal_action_notes", []))}</ul>
      </section>
      {unmatched_html}
      <section>
        <h2>Copy Performance Summary</h2>
        <button type="button" onclick="copyPerformanceSummary()">Copy Performance Summary</button>
        <textarea id="performance-summary-markdown" class="brief-copy-box" readonly>{_escape(summary_markdown)}</textarea>
      </section>
    """


def _performance_saved_notice(report):
    return f"""<section>
        <h2>Saved Performance Report</h2>
        <p>report_id: {_escape(report.get("report_id"))}</p>
        <p>Creative IDs can be matched against generated creative briefs by ID. Full linking can be added later.</p>
        <a href="/performance/history/{_escape(report.get("report_id"))}">View Saved Report</a>
        · <a href="/performance/history">View Performance History</a>
      </section>"""


def _performance_history_html(reports):
    cards = []
    for report in reports:
        cards.append(
            f"""<article class="history-card">
              <h2>{_escape(report.get("report_id"))}</h2>
              <p>created_at: {_escape(report.get("created_at"))}</p>
              <p>total spend: {_format_money(report.get("total_spend"))}</p>
              <p>matched creative count: {_escape(report.get("matched_creative_count"))}</p>
              <p>unmatched row count: {_escape(report.get("unmatched_row_count"))}</p>
              <p>SCALE_CANDIDATE: {_escape(report.get("scale_candidate_count"))}</p>
              <p>NEEDS_RECUT: {_escape(report.get("needs_recut_count"))}</p>
              <p>PAUSE: {_escape(report.get("pause_count"))}</p>
              <p>CHECK_LANDING_PAGE: {_escape(report.get("check_landing_page_count"))}</p>
              <a href="/performance/history/{_escape(report.get("report_id"))}">View Report</a>
            </article>"""
        )
    body = "\n".join(cards) or "<p>No saved performance reports yet.</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Performance Reports</title>{_history_style()}</head>
<body><main>
  <nav><a href="/performance">Back to Performance Analyzer</a> · <a href="/">Back to Generator</a></nav>
  <h1>Performance Reports</h1>
  <p>Saved local CSV analysis reports for internal media buyer and project review.</p>
  {body}
</main></body></html>"""


def _performance_report_detail_html(report):
    results = _performance_results_html(report.get("aggregated", {}), report.get("summary", {}), None)
    next_round = build_next_round_recommendations(report)
    next_round_markdown = next_round_plan_markdown(next_round)
    brief_request = build_next_round_brief_request(report, next_round)
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Performance Report Detail</title>{_history_style()}</head>
<body><main>
  <nav><a href="/performance/history">Back to Performance History</a> · <a href="/performance">Analyze New CSV</a></nav>
  <h1>Performance Report Detail</h1>
  <p>report_id: {_escape(report.get("report_id"))}</p>
  <p>created_at: {_escape(report.get("created_at"))}</p>
  {results}
  {_next_round_recommendations_html(next_round, next_round_markdown)}
  {_next_round_brief_request_html(brief_request)}
  <section>
    <h2>Raw CSV</h2>
    <details open><summary>Raw CSV Preview</summary><pre>{_escape(report.get("raw_csv_preview", ""))}</pre></details>
  </section>
  <script>
    async function copyPerformanceSummary() {{
      const target = document.getElementById('performance-summary-markdown');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(target.value);
      }} else {{
        document.execCommand('copy');
      }}
    }}
    async function copyNextRoundPlan() {{
      const target = document.getElementById('next-round-plan-markdown');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(target.value);
      }} else {{
        document.execCommand('copy');
      }}
    }}
    async function copyNextRoundRequest() {{
      const target = document.getElementById('next-round-request-markdown');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(target.value);
      }} else {{
        document.execCommand('copy');
      }}
    }}
  </script>
</main></body></html>"""


def _next_round_recommendations_html(recommendations, markdown):
    return f"""<section>
    <h2>Next Round Creative Recommendations</h2>
    <h3>Summary</h3>
    <div class="grid">
      {_kv_card("report_id", recommendations.get("summary", {}).get("report_id"))}
      {_kv_card("creative_count", recommendations.get("summary", {}).get("creative_count"))}
      {_kv_card("planning note", recommendations.get("summary", {}).get("message"))}
    </div>
    {_recommendation_group_html("Scale Candidates", recommendations.get("scale_candidates", []))}
    {_recommendation_group_html("Keep Testing", recommendations.get("keep_testing", []))}
    {_recommendation_group_html("Needs Recut", recommendations.get("needs_recut", []))}
    {_recommendation_group_html("Copy / CTA Tests", recommendations.get("copy_or_cta_tests", []))}
    {_recommendation_group_html("Landing Page Checks", recommendations.get("landing_page_checks", []))}
    {_recommendation_group_html("Pause", recommendations.get("pause", []))}
    <h3>Next Round Angles</h3>
    {_html_list(recommendations.get("next_round_angles", []))}
    <h3>Creative Brief Requests</h3>
    <p hidden>creative_brief_requests</p>
    {_html_list(recommendations.get("creative_brief_requests", []))}
    <h3>Internal Notes</h3>
    {_html_list(recommendations.get("internal_notes", []))}
    <h3>Copy Next Round Plan</h3>
    <button type="button" onclick="copyNextRoundPlan()">Copy Next Round Plan</button>
    <textarea id="next-round-plan-markdown" class="brief-copy-box" readonly>{_escape(markdown)}</textarea>
  </section>"""


def _recommendation_group_html(title, items):
    if not items:
        return f"<h3>{_escape(title)}</h3><p>None for now.</p>"
    cards = []
    for item in items:
        cards.append(
            f"""<article class="history-card">
              <h4>{_escape(item.get("creative_id"))} · {_escape(item.get("current_recommendation"))}</h4>
              <p>priority: {_escape(item.get("priority"))}</p>
              <p>reason: {_escape(item.get("reason"))}</p>
              <p>next_action: {_escape(item.get("next_action"))}</p>
              <p>suggested_variation: {_escape(item.get("suggested_variation"))}</p>
            </article>"""
        )
    return f"<h3>{_escape(title)}</h3>{''.join(cards)}"


def _next_round_brief_request_html(brief_request):
    structured = brief_request.get("structured", {})
    return f"""<section>
    <h2>Next Round Creative Brief Request</h2>
    <p>This request is for internal media buyers and creative producers. It does not generate new creatives automatically.</p>
    <div class="grid">
      {_kv_card("High priority actions", len(structured.get("priority_actions", {}).get("High", [])))}
      {_kv_card("Generation requests", len(structured.get("generation_requests", [])))}
      {_kv_card("Suggested Naming", ", ".join(structured.get("suggested_naming", [])[:3]))}
    </div>
    <button type="button" onclick="copyNextRoundRequest()">Copy Next Round Request</button>
    <textarea id="next-round-request-markdown" class="brief-copy-box" readonly>{_escape(brief_request.get("markdown", ""))}</textarea>
  </section>"""


def _html_list(items):
    if not items:
        return "<p>None for now.</p>"
    return f"<ul>{''.join(f'<li>{_escape(item)}</li>' for item in items)}</ul>"


def _performance_report_not_found_html(report_id):
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Performance report not found</title>{_history_style()}</head>
<body><main><h1>Performance report not found</h1><p>No saved Performance Report for {_escape(report_id)}.</p><a href="/performance/history">Back to Performance History</a></main></body></html>"""


def _performance_summary_markdown(summary, creatives):
    lines = [
        "# Performance Summary",
        "",
        f"- matched creatives: {summary.get('total_creatives_matched')}",
        f"- unmatched rows: {summary.get('missing_creative_id_rows_count')}",
        f"- total spend: {_format_money(summary.get('total_spend'))}",
        f"- best creative by CTR: {_summary_best(summary.get('best_creative_by_ctr'))}",
        f"- best creative by registrations: {_summary_best(summary.get('best_creative_by_registrations'))}",
        f"- best creative by deposits: {_summary_best(summary.get('best_creative_by_deposits'))}",
        "",
        "## Creative Actions",
    ]
    for creative_id, metrics in creatives.items():
        lines.extend(
            [
                "",
                f"### {creative_id}",
                f"- recommendation: {metrics.get('recommendation')}",
                f"- reason: {metrics.get('reason')}",
                f"- CTR: {_format_percent(metrics.get('ctr'))}",
                f"- CPC: {_format_money(metrics.get('cpc'))}",
                f"- CPM: {_format_money(metrics.get('cpm'))}",
                f"- CPA registration: {_format_money(metrics.get('cpa_registration'))}",
                f"- video 3s rate: {_format_percent(metrics.get('video_3s_rate'))}",
                f"- action: {metrics.get('action')}",
            ]
        )
    lines.extend(["", "## Internal Action Notes"])
    lines.extend(f"- {note}" for note in summary.get("internal_action_notes", []))
    return "\n".join(lines)


def _kv_card(label, value):
    return f"<div><b>{_escape(label)}</b><br>{_escape(value)}</div>"


def _summary_best(value):
    if not value:
        return "n/a"
    metric_key = next((key for key in value if key != "creative_id"), "")
    metric_value = value.get(metric_key)
    if metric_key in ("ctr", "link_ctr"):
        formatted = _format_percent(metric_value)
    else:
        formatted = _format_number(metric_value)
    return f"{value.get('creative_id')} ({metric_key}: {formatted})"


def _format_money(value):
    return "n/a" if value is None else f"${float(value):.2f}"


def _format_percent(value):
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def _format_number(value):
    if value is None:
        return "n/a"
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.2f}"


def _homepage_html():
    profile_requests = {
        profile["profile_id"]: profile_to_generation_request(profile["profile_id"])
        for profile in list_product_profiles()
    }
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
    .demo-actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0 12px; }
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
    textarea.brief-copy-box { min-height: 420px; margin-top: 8px; background: #101828; color: #e6edf7; border-color: #101828; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
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
    <section class="section">
      <h2>Internal Workflow Navigation</h2>
      <div class="grid">
        <a href="/">Generate Creatives</a>
        <a href="/history">Generation History</a>
        <a href="/performance">Performance CSV Analyzer</a>
        <a href="/performance/history">Performance Reports</a>
        <span>README / Operator Guide: docs/internal_operator_guide.md</span>
      </div>
    </section>
    <section class="section">
      <h2>Product Profiles</h2>
      <button type="button" onclick="fillProfile('spikex_brazil')">Use Spikex Brazil Profile</button>
    </section>
    <div class="demo-actions">
      <button type="button" onclick="fillDemo('spikex')">Spikex Brazil Demo</button>
      <button type="button" onclick="fillDemo('blocked')">BLOCKED Risk Demo</button>
      <button type="button" onclick="clearForm()">Clear Form</button>
    </div>
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
      <input type="hidden" name="profile_id" value="">
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
    const briefLine = (label, value) => value || value === 0 || value === false ? `- ${label}: ${formatBriefValue(value)}` : '';
    const formatBriefValue = (value) => Array.isArray(value) ? value.join(' / ') : String(value ?? '');
    const alphaCode = (value, length, fallback) => {
      const chars = String(value || '').match(/[A-Za-z0-9]/g) || [];
      return chars.length ? chars.slice(0, length).join('').toUpperCase().padEnd(length, 'X') : fallback;
    };
    const productCode = (value) => String(value || '').trim().toLowerCase() === 'spikex' ? 'SPK' : alphaCode(value, 3, 'XXX');
    const countryCode = (value) => {
      const normalized = String(value || '').trim().toLowerCase();
      if (normalized === 'brazil') return 'BR';
      if (['united states', 'usa', 'us'].includes(normalized)) return 'US';
      return alphaCode(value, 2, 'XX');
    };
    const platformCode = (value) => {
      const normalized = String(value || '').trim().toLowerCase();
      if (['facebook ads', 'facebook'].includes(normalized)) return 'FB';
      if (['tiktok ads', 'tiktok'].includes(normalized)) return 'TT';
      if (normalized === 'kwai') return 'KW';
      if (['google ads', 'google'].includes(normalized)) return 'GG';
      return alphaCode(value, 2, 'XX');
    };
    const compactDate = () => new Date().toISOString().slice(0, 10).replaceAll('-', '');
    const creativeId = (summary, index) => `${productCode(summary["产品"] || form.product.value)}-${countryCode(summary["国家"] || form.country.value)}-${platformCode(summary["平台"] || form.platform.value)}-${compactDate()}-C${String(index + 1).padStart(3, '0')}`;
    const enrichConcepts = (concepts, summary) => (concepts || []).map((concept, index) => ({...concept, creative_id: creativeId(summary, index)}));
    const productProfiles = __PRODUCT_PROFILE_REQUESTS__;
    let activeProductFacts = [];
    const demos = {
      spikex: {
        industry: 'crypto exchange',
        product: 'Spikex',
        platform: 'Facebook Ads',
        country: 'Brazil',
        language: 'Brazilian Portuguese',
        audience: 'Brazilian retail traders interested in crypto, stocks, copy trading and AI trading tools',
        selling_points: 'AI copy trading, crypto trading, US stocks trading, fast onboarding, beginner-friendly trading experience',
        duration: '15',
        campaign_rules: 'Avoid unrealistic financial promises, avoid exaggerated claims, follow platform ad policy, include risk-aware language',
        forbidden_claims: 'guaranteed profit, risk-free, no loss',
        restrictions: 'guaranteed profit, risk-free, no loss',
        demand: 'Generate 5 short video ad concepts with hooks, scripts, voiceover, captions and Runway prompts'
      },
      blocked: {
        industry: 'crypto exchange',
        product: 'Spikex',
        platform: 'Facebook Ads',
        country: 'Brazil',
        language: 'Brazilian Portuguese',
        audience: 'Brazilian retail traders interested in crypto',
        selling_points: 'guaranteed profit, risk-free trading, no loss',
        duration: '15',
        campaign_rules: 'Follow platform ad policy',
        forbidden_claims: 'none',
        restrictions: 'none',
        demand: 'Generate short video ad concepts'
      }
    };

    function fillDemo(name) {
      activeProductFacts = [];
      Object.entries(demos[name]).forEach(([key, value]) => {
        if (form[key]) form[key].value = value;
      });
      if (form.profile_id) form.profile_id.value = '';
      statusBox.className = 'status';
      statusBox.textContent = '等待生成';
    }

    function fillProfile(profileId) {
      const profile = productProfiles[profileId];
      if (!profile) return;
      const mapping = {
        "行业": "industry",
        "产品": "product",
        "投放平台": "platform",
        "国家": "country",
        "语言": "language",
        "目标人群": "audience",
        "卖点": "selling_points",
        "活动规则": "campaign_rules",
        "限制词": "forbidden_claims",
        "需求": "demand"
      };
      Object.entries(mapping).forEach(([source, target]) => {
        if (form[target]) form[target].value = profile[source] || '';
      });
      if (form.restrictions) form.restrictions.value = profile["限制词"] || '';
      if (form.duration) form.duration.value = '15';
      if (form.profile_id) form.profile_id.value = profile.profile_id || profileId;
      activeProductFacts = profile.product_facts || [];
      statusBox.className = 'status';
      statusBox.textContent = '等待生成';
    }

    function clearForm() {
      Array.from(form.elements).forEach((element) => {
        if (element.name) element.value = '';
      });
      activeProductFacts = [];
      statusBox.className = 'status';
      statusBox.textContent = '等待生成';
      output.textContent = '生成结果会显示在这里。';
    }

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
        "profile_id": form.profile_id.value,
        "product_facts": activeProductFacts,
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
      const concepts = enrichConcepts(content.video_ad_concepts || [], summary);
      const creativeBrief = renderCreativeBriefMarkdown(content, result);
      const launchBrief = renderMediaBuyerLaunchBrief(summary, concepts);
      statusBox.className = 'status generated';
      statusBox.textContent = `GENERATED generation_id=${result.generation_id} 素材内容`;
      output.innerHTML = `
        <section class="section"><h2>Saved to History</h2><p>Saved to History · <a href="/history">View History</a></p></section>
        <section class="section">${renderStatus(result, summary)}</section>
        <section class="section"><h2>5 套素材卡片</h2>${concepts.map(renderCreativeCard).join('')}</section>
        <section class="section"><h2>Prompt 专区</h2>${concepts.map(renderPromptBlock).join('')}</section>
        <section class="section"><h2>Facebook Ads 文案专区</h2>${concepts.map(renderFacebookBlock).join('')}</section>
        <section class="section"><h2>评分报告区 scoring_report</h2>${renderScoring(content.scoring_report || {})}</section>
        <section class="section"><h2>制作建议区</h2>${renderKeyValues(content.media_production_notes || {})}</section>
        <section class="section"><h2>投放计划区 launch_plan</h2>${renderLaunchPlan(content.launch_plan || {})}</section>
        <section class="section"><h2>红线检查区 forbidden_claims_check</h2>${renderForbiddenCheck(content.forbidden_claims_check || {})}</section>
        <section class="section"><h2>Creative Brief Markdown</h2><button type="button" onclick="copyFullBrief()">Copy Full Brief</button><textarea id="creative-brief-markdown" class="brief-copy-box" readonly>${escapeHtml(creativeBrief)}</textarea></section>
        <section class="section"><h2>Media Buyer Launch Brief</h2><button type="button" onclick="copyLaunchBrief()">Copy Launch Brief</button><textarea id="media-buyer-launch-brief" class="brief-copy-box launch-brief-copy-box" readonly>${escapeHtml(launchBrief)}</textarea></section>
        ${renderRawJson(result)}
      `;
    }

    async function copyFullBrief() {
      const target = document.getElementById('creative-brief-markdown');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(target.value);
      } else {
        document.execCommand('copy');
      }
    }

    async function copyLaunchBrief() {
      const target = document.getElementById('media-buyer-launch-brief');
      if (!target) return;
      target.select();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(target.value);
      } else {
        document.execCommand('copy');
      }
    }

    function renderCreativeBriefMarkdown(content, result) {
      const summary = content.campaign_summary || {};
      const concepts = enrichConcepts(content.video_ad_concepts || [], summary);
      const report = content.scoring_report || {};
      const notes = content.media_production_notes || {};
      const launchPlan = content.launch_plan || {};
      const forbiddenCheck = content.forbidden_claims_check || {};
      const lines = ['# Creative Brief', '', '## Campaign Summary'];
      [
        briefLine('generation_id', result.generation_id),
        briefLine('product', summary["产品"]),
        briefLine('industry', form.industry.value),
        briefLine('platform', summary["平台"]),
        briefLine('country', summary["国家"]),
        briefLine('language', summary["投放语言"]),
        briefLine('audience', summary["目标人群"]),
        briefLine('selling points', summary["核心卖点"]),
        briefLine('campaign rules summary', form.campaign_rules.value)
      ].filter(Boolean).forEach((line) => lines.push(line));
      if (Array.isArray(result.product_facts) && result.product_facts.length) {
        lines.push('', '### Product Facts');
        result.product_facts.forEach((fact) => lines.push(`- ${fact}`));
      }

      lines.push('', '## Creative Concepts');
      concepts.forEach((concept) => {
        lines.push('', `### ${formatBriefValue(concept.concept_id)} ${formatBriefValue(concept.concept_name)}`.trim());
        lines.push(`- Creative ID: ${concept.creative_id}`);
        [
          'creative_id',
          'target_angle',
          'hook',
          'scene_breakdown',
          '15s_script',
          'voiceover',
          'captions',
          'visual_style',
          'runway_prompt',
          'elevenlabs_prompt',
          'facebook_primary_text',
          'facebook_headline',
          'facebook_description',
          'compliance_notes'
        ].forEach((key) => {
          const line = briefLine(key, concept[key]);
          if (line) lines.push(line);
        });
      });

      lines.push('', '## Scoring Report');
      [
        'total_score',
        'hook_score',
        'clarity_score',
        'compliance_score',
        'localization_score',
        'conversion_potential_score',
        'improvement_suggestions'
      ].forEach((key) => {
        const line = briefLine(key, report[key]);
        if (line) lines.push(line);
      });

      lines.push('', '## Media Production Notes');
      Object.entries(notes).forEach(([key, value]) => {
        const line = briefLine(key, value);
        if (line) lines.push(line);
      });

      lines.push('', '## Launch Plan');
      Object.entries(launchPlan).forEach(([key, value]) => {
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          lines.push(`- ${key}: ${Object.entries(value).map(([innerKey, innerValue]) => `${innerKey}: ${formatBriefValue(innerValue)}`).join(' / ')}`);
        } else {
          const line = briefLine(key, value);
          if (line) lines.push(line);
        }
      });

      lines.push('', '## Forbidden Claims Check');
      Object.entries(forbiddenCheck).forEach(([key, value]) => {
        const line = briefLine(key, value);
        if (line) lines.push(line);
      });
      return lines.join('\\n');
    }

    function renderMediaBuyerLaunchBrief(summary, concepts) {
      const lines = [
        '# Media Buyer Launch Brief',
        '',
        '## Campaign Setup Summary',
        briefLine('product', summary["产品"] || form.product.value),
        briefLine('profile/client', form.profile_id.value || form.product.value),
        briefLine('platform', summary["平台"] || form.platform.value),
        briefLine('country', summary["国家"] || form.country.value),
        briefLine('language', summary["投放语言"] || form.language.value),
        briefLine('audience', summary["目标人群"] || form.audience.value),
        briefLine('campaign rules summary', form.campaign_rules.value),
        '',
        '## Creative Launch Table'
      ].filter((line) => line !== '');
      concepts.forEach((concept) => {
        lines.push('', `### ${concept.creative_id} ${formatBriefValue(concept.concept_name)}`);
        [
          briefLine('creative_id', concept.creative_id),
          briefLine('concept_name', concept.concept_name),
          briefLine('target_angle', concept.target_angle),
          briefLine('hook', concept.hook),
          briefLine('recommended placement / platform', summary["平台"] || form.platform.value),
          briefLine('recommended test intent', 'Test hook clarity, user fit, and risk-aware platform understanding.'),
          briefLine('primary metric to watch', 'CTR'),
          briefLine('secondary metrics to watch', '3s view rate / 50% view rate / registration / deposit / CPA'),
          briefLine('risk note', 'Pause or rewrite if wording implies guaranteed profit, no risk, or unrealistic outcomes.')
        ].filter(Boolean).forEach((line) => lines.push(line));
      });
      lines.push(
        '',
        '## Launch Checklist',
        '- Confirm product facts',
        '- Confirm landing page matches ad claim',
        '- Confirm no guaranteed profit / no risk claim',
        '- Confirm video file name uses creative_id',
        '- Confirm captions match voiceover',
        '- Confirm Facebook copy matches approved brief',
        '- Confirm tracking / pixel / event setup before launch',
        '',
        '## Decision Rules',
        '- High CTR but low registration: check landing page / offer match',
        '- Low 3s view rate: improve first 3 seconds hook',
        '- High 3s view but low click: improve CTA or ad copy',
        '- High click but no deposit: review onboarding and trust signals',
        '- Compliance concern: pause and rewrite risky wording'
      );
      return lines.join('\\n');
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
          ${field('Creative ID', concept.creative_id)}
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
        <b>Primary Text</b>${copyBox(concept.facebook_primary_text)}
        <b>Headline</b>${copyBox(concept.facebook_headline)}
        <b>Description</b>${copyBox(concept.facebook_description)}
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
        <p>Saved to History · <a href="/history">View History</a></p>
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
</html>""".replace("__PRODUCT_PROFILE_REQUESTS__", json.dumps(profile_requests, ensure_ascii=False))


if __name__ == "__main__":
    main()
