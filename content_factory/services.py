from content_factory.db import dumps_json, fetch_one, insert_record, loads_json


BLOCKING_AUDIT_STATUSES = ("HUMAN_REQUIRED", "FATAL_FAILED")


def run_content_pipeline(conn, provider, request):
    product_id = _create_product(conn, request)
    product = _row_to_dict(fetch_one(conn, "SELECT * FROM products WHERE id = ?", (product_id,)))

    raw_demand = request.get("需求") or _build_raw_demand(request)
    structured = provider.structure_demand(raw_demand, product)
    structured["语言"] = request.get("语言", "中文")
    demand_id = insert_record(
        conn,
        "demand_intakes",
        {
            "product_id": product_id,
            "raw_input": raw_demand,
            "structured_json": dumps_json(structured),
            "missing_info": dumps_json(structured.get("缺失信息", [])),
        },
    )
    demand = {"id": demand_id, "raw_input": raw_demand, "structured": structured}

    materials = _create_materials(conn, product_id, request.get("素材", []))
    audit = provider.audit_materials(product, demand, materials)
    audit_id = insert_record(
        conn,
        "material_audits",
        {
            "product_id": product_id,
            "demand_id": demand_id,
            "status": audit["status"],
            "audit_json": dumps_json(audit),
        },
    )

    if audit["status"] in BLOCKING_AUDIT_STATUSES:
        return {
            "状态": "BLOCKED",
            "product_id": product_id,
            "demand_id": demand_id,
            "audit_id": audit_id,
            "generation_id": None,
            "素材审核": audit,
            "阻断原因": audit.get("risks") or audit.get("missing_materials", []),
        }

    generation = provider.generate_content(product, demand, materials, [], audit)
    generation_id = insert_record(
        conn,
        "content_generations",
        {
            "product_id": product_id,
            "demand_id": demand_id,
            "audit_id": audit_id,
            "generation_json": dumps_json(generation),
        },
    )
    evaluation = provider.evaluate_generation(product, demand, generation, audit)
    insert_record(
        conn,
        "evaluation_reports",
        {
            "generation_id": generation_id,
            "score": evaluation["总分"],
            "report_json": dumps_json(evaluation),
        },
    )

    return {
        "状态": "GENERATED",
        "product_id": product_id,
        "demand_id": demand_id,
        "audit_id": audit_id,
        "generation_id": generation_id,
        "素材审核": audit,
        "素材内容": generation,
        "评分报告": evaluation,
    }


def get_generation_result(conn, generation_id):
    generation_row = fetch_one(conn, "SELECT * FROM content_generations WHERE id = ?", (generation_id,))
    if generation_row is None:
        return None

    product = _row_to_dict(fetch_one(conn, "SELECT * FROM products WHERE id = ?", (generation_row["product_id"],)))
    demand_row = fetch_one(conn, "SELECT * FROM demand_intakes WHERE id = ?", (generation_row["demand_id"],))
    audit_row = fetch_one(conn, "SELECT * FROM material_audits WHERE id = ?", (generation_row["audit_id"],))
    evaluation_row = fetch_one(
        conn,
        "SELECT * FROM evaluation_reports WHERE generation_id = ? ORDER BY id DESC LIMIT 1",
        (generation_id,),
    )
    performance_rows = conn.execute(
        "SELECT * FROM ad_performance_logs WHERE generation_id = ? ORDER BY id",
        (generation_id,),
    ).fetchall()

    return {
        "product": product,
        "demand": {
            "id": demand_row["id"],
            "raw_input": demand_row["raw_input"],
            "structured": loads_json(demand_row["structured_json"], {}),
            "missing_info": loads_json(demand_row["missing_info"], []),
        },
        "audit": loads_json(audit_row["audit_json"], {}),
        "generation": loads_json(generation_row["generation_json"], {}),
        "evaluation": loads_json(evaluation_row["report_json"], {}) if evaluation_row else None,
        "performance_logs": [
            {
                "id": row["id"],
                "metrics": _performance_metrics(row),
                "analysis": loads_json(row["analysis_json"], {}),
            }
            for row in performance_rows
        ],
    }


def record_performance_feedback(conn, provider, generation_id, metrics):
    generation_row = fetch_one(conn, "SELECT * FROM content_generations WHERE id = ?", (generation_id,))
    if generation_row is None:
        raise ValueError("generation_id 不存在")

    generation = loads_json(generation_row["generation_json"], {})
    analysis = provider.analyze_performance(generation, metrics)
    insert_record(
        conn,
        "ad_performance_logs",
        {
            "generation_id": generation_id,
            "spend": metrics.get("spend", 0),
            "impressions": metrics.get("impressions", 0),
            "cpm": metrics.get("cpm", 0),
            "link_clicks": metrics.get("link_clicks", 0),
            "ctr": metrics.get("ctr", 0),
            "registrations": metrics.get("registrations", 0),
            "recharges": metrics.get("recharges", 0),
            "cpa": metrics.get("cpa", 0),
            "play_3s": metrics.get("play_3s", 0),
            "play_50": metrics.get("play_50", 0),
            "play_95": metrics.get("play_95", 0),
            "play_100": metrics.get("play_100", 0),
            "analysis_json": dumps_json(analysis),
        },
    )
    return {"generation_id": generation_id, "投放分析建议": analysis}


def _create_product(conn, request):
    return insert_record(
        conn,
        "products",
        {
            "name": request.get("产品") or "未命名产品",
            "product_url": request.get("产品链接", ""),
            "country": request.get("国家", ""),
            "category": request.get("行业", ""),
            "platform": request.get("投放平台", ""),
            "selling_points": request.get("卖点", ""),
            "campaign_rules": request.get("活动规则", ""),
            "forbidden_claims": request.get("限制词", ""),
            "compliance_redlines": request.get("合规红线", "必须使用真实logo、真实界面、真实活动规则"),
            "notes": request.get("备注", ""),
        },
    )


def _create_materials(conn, product_id, materials):
    created = []
    for material in materials:
        material_id = insert_record(
            conn,
            "material_assets",
            {
                "product_id": product_id,
                "name": material.get("name", "未命名素材"),
                "material_type": material.get("material_type", material.get("type", "")),
                "source": material.get("source", "人工输入"),
                "scenario": material.get("scenario", ""),
                "grade": material.get("grade", "真实素材"),
                "reusable": int(material.get("reusable", 0)),
                "compliant": int(material.get("compliant", 1)),
                "file_path": material.get("file_path", ""),
                "external_url": material.get("external_url", ""),
                "notes": material.get("notes", ""),
            },
        )
        saved = dict(material)
        saved["id"] = material_id
        created.append(saved)
    return created


def _build_raw_demand(request):
    parts = [
        request.get("行业", ""),
        request.get("产品", ""),
        request.get("目标人群", ""),
        request.get("投放平台", ""),
        request.get("语言", ""),
        request.get("卖点", ""),
    ]
    return "，".join(part for part in parts if part)


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _performance_metrics(row):
    return {
        "spend": row["spend"],
        "impressions": row["impressions"],
        "cpm": row["cpm"],
        "link_clicks": row["link_clicks"],
        "ctr": row["ctr"],
        "registrations": row["registrations"],
        "recharges": row["recharges"],
        "cpa": row["cpa"],
        "play_3s": row["play_3s"],
        "play_50": row["play_50"],
        "play_95": row["play_95"],
        "play_100": row["play_100"],
    }
