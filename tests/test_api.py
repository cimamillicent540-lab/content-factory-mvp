import json
import os
import tempfile
import threading
import unittest

from content_factory.api import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.app = create_app(os.path.join(self.tmpdir.name, "api.sqlite3"))

    def test_health_returns_ok(self):
        status, headers, body = self.app.handle("GET", "/health")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(payload["status"], "ok")

    def test_generate_returns_chinese_payload_for_valid_request(self):
        status, _headers, body = self.app.handle("POST", "/generate", self._valid_request())
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "GENERATED")
        self.assertIsInstance(payload["generation_id"], int)
        self.assertEqual(payload["结构化需求"]["平台"], "Facebook")
        self.assertEqual(payload["红线审核结果"]["status"], "PASS")
        self.assertIn("素材方向", payload["素材内容"])
        self.assertIn("Check", payload["素材内容"]["旁白"])
        self.assertNotIn("中文" + "素材内容", payload)
        self.assertEqual(payload["100分评分报告"]["总分"], 100)
        self.assertIn("表现判断", payload["投放分析建议"])

    def test_generate_can_run_from_request_thread(self):
        result = {}

        def call_api():
            result["response"] = self.app.handle("POST", "/generate", self._valid_request())

        thread = threading.Thread(target=call_api)
        thread.start()
        thread.join()
        status, _headers, body = result["response"]
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "GENERATED")

    def test_generate_returns_blocked_without_content_when_redline_hit(self):
        request = self._valid_request()
        request["需求"] = "做一条保证收益稳赚的广告"

        status, _headers, body = self.app.handle("POST", "/generate", request)
        payload = json.loads(body)

        self.assertEqual(status, 409)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIsNone(payload["generation_id"])
        self.assertIn("保证收益", " ".join(payload["阻断原因"]))
        self.assertNotIn("中文" + "素材内容", payload)
        self.assertNotIn("素材内容", payload)

    def test_get_generation_by_id_returns_saved_result(self):
        _status, _headers, body = self.app.handle("POST", "/generate", self._valid_request())
        generated = json.loads(body)

        status, _headers, body = self.app.handle("GET", f"/generations/{generated['generation_id']}")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "FOUND")
        self.assertEqual(payload["generation_id"], generated["generation_id"])
        self.assertIn("素材内容", payload)
        self.assertNotIn("中文" + "素材内容", payload)

    def test_feedback_endpoint_saves_analysis(self):
        _status, _headers, body = self.app.handle("POST", "/generate", self._valid_request())
        generated = json.loads(body)

        status, _headers, body = self.app.handle(
            "POST",
            f"/generations/{generated['generation_id']}/feedback",
            {"ctr": 0.8, "cpa": 20, "play_3s": 1000, "play_50": 200},
        )
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "RECORDED")
        self.assertIn("下一轮动作", payload["投放分析建议"])

    def test_unknown_route_returns_404(self):
        status, _headers, body = self.app.handle("GET", "/missing")
        payload = json.loads(body)

        self.assertEqual(status, 404)
        self.assertEqual(payload["status"], "NOT_FOUND")

    def _valid_request(self):
        return {
            "行业": "交易所",
            "产品": "加密货币跟单产品",
            "投放平台": "Facebook",
            "国家": "巴西",
            "语言": "en",
            "目标人群": "新用户",
            "卖点": "注册奖励、跟单、快速开始",
            "活动规则": "新人完成注册可参与活动",
            "限制词": "稳赚，保证收益，官方背书",
            "需求": "给Facebook巴西新用户做一条15秒注册转化素材",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }
