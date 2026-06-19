import argparse
import json

from content_factory.ai_provider import MockAIProvider
from content_factory.config import load_settings
from content_factory.db import connect, init_db
from content_factory.services import (
    get_generation_result,
    record_performance_feedback,
    run_content_pipeline,
)


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings({})
    database_path = args.database_path or settings.database_path

    conn = connect(database_path)
    init_db(conn)
    provider = MockAIProvider()

    request = _request_from_args(args)
    pipeline_result = run_content_pipeline(conn, provider, request)

    if pipeline_result["状态"] == "BLOCKED":
        _print_json(
            {
                "状态": "BLOCKED",
                "generation_id": None,
                "结构化需求": _demand_from_pipeline(conn, pipeline_result["demand_id"]),
                "红线审核结果": pipeline_result["素材审核"],
                "阻断原因": pipeline_result["阻断原因"],
            }
        )
        return 2

    performance = record_performance_feedback(
        conn,
        provider,
        pipeline_result["generation_id"],
        _performance_metrics_from_args(args),
    )
    saved = get_generation_result(conn, pipeline_result["generation_id"])
    _print_json(
        {
            "状态": "GENERATED",
            "generation_id": pipeline_result["generation_id"],
            "结构化需求": saved["demand"]["structured"],
            "红线审核结果": saved["audit"],
            "素材内容": saved["generation"],
            "100分评分报告": saved["evaluation"],
            "投放分析建议": performance["投放分析建议"],
        }
    )
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(description="海外投流素材内容工厂本地 CLI Demo")
    parser.add_argument("--database-path", default="")
    parser.add_argument("--industry", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--language", default="中文")
    parser.add_argument("--audience", required=True)
    parser.add_argument("--selling-points", required=True)
    parser.add_argument("--duration", default="15秒")
    parser.add_argument("--campaign-rules", default="新人完成注册可参与活动")
    parser.add_argument("--forbidden-claims", default="稳赚，保证收益，官方背书")
    parser.add_argument("--demand", default="")
    parser.add_argument("--ctr", type=float, default=0.8)
    parser.add_argument("--cpa", type=float, default=20)
    parser.add_argument("--play-3s", type=int, default=1000)
    parser.add_argument("--play-50", type=int, default=300)
    return parser


def _request_from_args(args):
    demand = args.demand or (
        f"给{args.platform}{args.country}{args.audience}做一条{args.duration}注册转化素材，"
        f"卖点是{args.selling_points}"
    )
    return {
        "行业": args.industry,
        "产品": args.product,
        "目标人群": args.audience,
        "投放平台": args.platform,
        "语言": args.language,
        "国家": args.country,
        "卖点": args.selling_points,
        "活动规则": args.campaign_rules,
        "限制词": args.forbidden_claims,
        "需求": demand,
        "素材": [
            {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
            {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
            {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
        ],
    }


def _performance_metrics_from_args(args):
    return {
        "ctr": args.ctr,
        "cpa": args.cpa,
        "play_3s": args.play_3s,
        "play_50": args.play_50,
    }


def _demand_from_pipeline(conn, demand_id):
    row = conn.execute("SELECT structured_json FROM demand_intakes WHERE id = ?", (demand_id,)).fetchone()
    return json.loads(row["structured_json"]) if row else {}


def _print_json(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
