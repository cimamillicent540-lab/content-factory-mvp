import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from content_factory.ai_provider import MockAIProvider
from content_factory.config import load_settings
from content_factory.db import connect, init_db
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
        self.provider = MockAIProvider()

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
  <title>海外投流素材内容工厂</title>
  <style>
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7fb;
      color: #172033;
    }
    body { margin: 0; }
    main { max-width: 1120px; margin: 0 auto; padding: 28px 20px 48px; }
    h1 { font-size: 28px; margin: 0 0 6px; }
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
    input, textarea {
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
      border: 0;
      border-radius: 6px;
      padding: 10px 16px;
      background: #155eef;
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
    .status { margin-top: 14px; font-weight: 700; }
    .blocked { color: #b42318; }
    .generated { color: #027a48; }
    @media (max-width: 760px) {
      form { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <main>
    <h1>海外投流素材内容工厂</h1>
    <p>填写素材需求，调用本地核心流程，输出多语言素材 JSON。</p>
    <form id="factory-form">
      <label>行业 industry
        <input name="industry" value="交易所" required>
      </label>
      <label>产品 product
        <input name="product" value="加密货币跟单产品" required>
      </label>
      <label>平台 platform
        <input name="platform" value="Facebook" required>
      </label>
      <label>国家 country
        <input name="country" value="巴西" required>
      </label>
      <label>语言 language
        <input name="language" value="中文" required>
      </label>
      <label>人群 audience
        <input name="audience" value="新用户" required>
      </label>
      <label class="wide">卖点 selling_points
        <input name="selling_points" value="注册奖励、跟单、快速开始" required>
      </label>
      <label>时长 duration
        <input name="duration" value="15秒" required>
      </label>
      <label>限制词/红线词 restrictions
        <input name="restrictions" value="稳赚，保证收益，官方背书" required>
      </label>
      <label class="wide">自定义需求 demand
        <textarea name="demand" placeholder="留空则根据字段自动生成需求"></textarea>
      </label>
      <div class="wide">
        <button type="submit">生成素材 JSON</button>
      </div>
    </form>
    <div id="status" class="status">等待生成</div>
    <pre id="output">生成结果会显示在这里。</pre>
  </main>
  <script>
    const form = document.getElementById('factory-form');
    const statusBox = document.getElementById('status');
    const output = document.getElementById('output');

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
        "限制词": form.restrictions.value,
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
      output.textContent = JSON.stringify(result, null, 2);
      if (result.status === 'BLOCKED') {
        statusBox.className = 'status blocked';
        statusBox.textContent = `BLOCKED：${(result["阻断原因"] || []).join('，')}`;
      } else {
        statusBox.className = 'status generated';
        statusBox.textContent = `GENERATED generation_id=${result.generation_id}`;
      }
    });
  </script>
</body>
</html>"""


if __name__ == "__main__":
    main()
