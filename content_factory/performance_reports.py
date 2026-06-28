import uuid
from datetime import datetime

from content_factory.db import dumps_json, loads_json
from content_factory.performance_analysis import (
    build_performance_summary,
    calculate_performance_metrics,
    parse_performance_csv,
)


def save_performance_report(conn, csv_text):
    report = build_performance_report(csv_text)
    conn.execute(
        """
        INSERT INTO performance_reports (report_id, report_json)
        VALUES (?, ?)
        """,
        (report["report_id"], dumps_json(report)),
    )
    conn.commit()
    row = conn.execute("SELECT created_at FROM performance_reports WHERE report_id = ?", (report["report_id"],)).fetchone()
    report["created_at"] = row["created_at"] if row else report["created_at"]
    _update_created_at(conn, report)
    return report


def list_performance_reports(conn, limit=50):
    rows = conn.execute(
        """
        SELECT report_id, report_json, created_at
        FROM performance_reports
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_report_card(row) for row in rows]


def get_performance_report(conn, report_id):
    row = conn.execute(
        """
        SELECT report_id, report_json, created_at
        FROM performance_reports
        WHERE report_id = ?
        """,
        (report_id,),
    ).fetchone()
    if row is None:
        return None
    report = loads_json(row["report_json"], {})
    report["created_at"] = row["created_at"]
    return report


def build_performance_report(csv_text):
    rows = parse_performance_csv(csv_text)
    aggregated = calculate_performance_metrics(rows)
    summary = build_performance_summary(aggregated)
    summary_markdown = performance_summary_markdown(summary, aggregated.get("creatives", {}))
    return {
        "report_id": _new_report_id(),
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_csv_text": csv_text,
        "raw_csv_preview": _preview(csv_text),
        "summary": summary,
        "aggregated": aggregated,
        "unmatched_rows_summary": {
            "count": aggregated.get("summary", {}).get("unmatched_row_count", 0),
            "rows": aggregated.get("unmatched_rows", []),
        },
        "internal_action_notes": summary.get("internal_action_notes", []),
        "summary_markdown": summary_markdown,
    }


def performance_summary_markdown(summary, creatives):
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


def _report_card(row):
    report = loads_json(row["report_json"], {})
    summary = report.get("summary", {})
    creatives = report.get("aggregated", {}).get("creatives", {})
    return {
        "report_id": row["report_id"],
        "created_at": row["created_at"],
        "total_spend": summary.get("total_spend", 0),
        "matched_creative_count": summary.get("total_creatives_matched", 0),
        "unmatched_row_count": summary.get("missing_creative_id_rows_count", 0),
        "scale_candidate_count": _count_recommendation(creatives, "SCALE_CANDIDATE"),
        "needs_recut_count": _count_recommendation(creatives, "NEEDS_RECUT"),
        "pause_count": _count_recommendation(creatives, "PAUSE"),
        "check_landing_page_count": _count_recommendation(creatives, "CHECK_LANDING_PAGE"),
    }


def _update_created_at(conn, report):
    conn.execute(
        "UPDATE performance_reports SET report_json = ? WHERE report_id = ?",
        (dumps_json(report), report["report_id"]),
    )
    conn.commit()


def _new_report_id():
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"perf-{timestamp}-{uuid.uuid4().hex[:8]}"


def _preview(csv_text, length=500):
    text = csv_text or ""
    return text if len(text) <= length else text[:length] + "\n..."


def _count_recommendation(creatives, recommendation):
    return sum(1 for metrics in creatives.values() if metrics.get("recommendation") == recommendation)


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
