import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from content_factory.cli import main


class CliTests(unittest.TestCase):
    def test_cli_outputs_generation_payload_for_valid_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "demo.sqlite3")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--database-path",
                        db_path,
                        "--industry",
                        "交易所",
                        "--product",
                        "加密货币跟单产品",
                        "--platform",
                        "Facebook",
                        "--country",
                        "巴西",
                        "--language",
                        "en",
                        "--audience",
                        "新用户",
                        "--selling-points",
                        "注册奖励、跟单、快速开始",
                        "--duration",
                        "15秒",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["状态"], "GENERATED")
        self.assertIsInstance(payload["generation_id"], int)
        self.assertEqual(payload["结构化需求"]["平台"], "Facebook")
        self.assertEqual(payload["红线审核结果"]["status"], "PASS")
        self.assertIn("素材方向", payload["素材内容"])
        self.assertIn("Check", payload["素材内容"]["旁白"])
        self.assertNotIn("中文" + "素材内容", payload)
        self.assertIn("总分", payload["100分评分报告"])
        self.assertIn("表现判断", payload["投放分析建议"])

    def test_cli_outputs_block_reason_without_generation_when_redline_hit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "demo.sqlite3")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--database-path",
                        db_path,
                        "--industry",
                        "交易所",
                        "--product",
                        "加密货币跟单产品",
                        "--platform",
                        "Facebook",
                        "--country",
                        "巴西",
                        "--language",
                        "中文",
                        "--audience",
                        "新用户",
                        "--selling-points",
                        "注册奖励、跟单、快速开始",
                        "--duration",
                        "15秒",
                        "--demand",
                        "做一条保证收益稳赚的广告",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["状态"], "BLOCKED")
        self.assertIsNone(payload["generation_id"])
        self.assertEqual(payload["红线审核结果"]["status"], "FATAL_FAILED")
        self.assertIn("保证收益", " ".join(payload["阻断原因"]))
        self.assertNotIn("中文" + "素材内容", payload)
        self.assertNotIn("素材内容", payload)
