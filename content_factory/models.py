AUDIT_STATUSES = ("PASS", "AUTO_REPAIR", "HUMAN_REQUIRED", "FATAL_FAILED")

MATERIAL_GRADES = (
    "真实素材",
    "AI可补素材",
    "视频工具可生成素材",
    "必须人工补充的红线素材",
)

ASSET_CATEGORIES = ("产品截图", "logo", "落地页截图", "后台截图", "历史素材")

EVALUATION_WEIGHTS = {
    "产品事实准确性": 20,
    "真实性与红线素材": 20,
    "场景与人群匹配": 15,
    "脚本与分镜质量": 15,
    "视频brief可执行性": 15,
    "合规与风险": 10,
    "复用价值": 5,
}
