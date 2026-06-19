# Overseas Ad Content Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Chinese-only MVP for an overseas ad creative content factory Agent with product facts, demand intake, benchmark deconstruction, material audit, content generation, final evaluation, and ad performance feedback.

**Architecture:** Use a dependency-free Python web app with server-rendered pages, SQLite persistence, local file uploads, and a replaceable AI provider interface. The app keeps the Agent pipeline explicit: demand structuring, material audit, content generation, evaluation, and performance analysis are separate service functions with saved records.

**Tech Stack:** Python 3 standard library, `http.server`, `sqlite3`, `unittest`, HTML/CSS/vanilla JavaScript, local `uploads/` storage.

---

## File Structure

- `app.py`: HTTP server entrypoint, route dispatch, static file serving, request parsing, and response helpers.
- `content_factory/__init__.py`: Package marker.
- `content_factory/config.py`: Environment-driven settings for database path, upload directory, host, port, and AI provider name.
- `content_factory/db.py`: SQLite connection, schema creation, small query helpers, and JSON serialization helpers.
- `content_factory/models.py`: Constants for audit statuses, material grades, asset categories, and score weights.
- `content_factory/ai_provider.py`: Provider interface and `MockAIProvider`.
- `content_factory/services.py`: Business workflows for creating records and enforcing audit-before-generation/evaluation-after-generation.
- `content_factory/views.py`: Server-rendered HTML pages and reusable UI components.
- `content_factory/sample_data.py`: Optional seed data for first-run demos.
- `tests/test_db.py`: Schema and database helper tests.
- `tests/test_ai_provider.py`: Mock provider output tests.
- `tests/test_services.py`: Pipeline and blocking-rule tests.
- `tests/test_http.py`: Minimal HTTP smoke tests.
- `README.md`: Setup, env vars, run, test, and future real-AI provider notes.
- `.env.example`: Safe configuration template with no secrets.
- `.gitignore`: Ignore runtime database, uploads, caches, env files, and visual brainstorming state.

## Task 1: Project Skeleton And Configuration

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `content_factory/__init__.py`
- Create: `content_factory/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write configuration tests**

Create `tests/test_config.py`:

```python
import os
import unittest

from content_factory.config import Settings, load_settings


class ConfigTests(unittest.TestCase):
    def test_default_settings_are_safe_for_local_mvp(self):
        settings = load_settings({})
        self.assertEqual(settings.database_path, "data/content_factory.sqlite3")
        self.assertEqual(settings.upload_dir, "uploads")
        self.assertEqual(settings.ai_provider, "mock")
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8000)

    def test_environment_overrides_are_supported(self):
        settings = load_settings(
            {
                "DATABASE_PATH": "tmp/test.sqlite3",
                "UPLOAD_DIR": "tmp/uploads",
                "AI_PROVIDER": "openai",
                "HOST": "0.0.0.0",
                "PORT": "8123",
            }
        )
        self.assertEqual(settings.database_path, "tmp/test.sqlite3")
        self.assertEqual(settings.upload_dir, "tmp/uploads")
        self.assertEqual(settings.ai_provider, "openai")
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 8123)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_config -v`

Expected: FAIL because `content_factory.config` does not exist.

- [ ] **Step 3: Implement configuration files**

Create `content_factory/__init__.py` as an empty package marker.

Create `content_factory/config.py`:

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_path: str
    upload_dir: str
    ai_provider: str
    host: str
    port: int


def load_settings(env=None):
    source = os.environ if env is None else env
    return Settings(
        database_path=source.get("DATABASE_PATH", "data/content_factory.sqlite3"),
        upload_dir=source.get("UPLOAD_DIR", "uploads"),
        ai_provider=source.get("AI_PROVIDER", "mock"),
        host=source.get("HOST", "127.0.0.1"),
        port=int(source.get("PORT", "8000")),
    )
```

Create `.env.example`:

```bash
DATABASE_PATH=data/content_factory.sqlite3
UPLOAD_DIR=uploads
AI_PROVIDER=mock
HOST=127.0.0.1
PORT=8000

# Future real-model provider support. Do not commit real secrets.
# OPENAI_API_KEY=
```

Create `.gitignore`:

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
data/
uploads/
.superpowers/
```

- [ ] **Step 4: Run configuration tests**

Run: `python3 -m unittest tests.test_config -v`

Expected: PASS.

## Task 2: SQLite Schema

**Files:**
- Create: `content_factory/db.py`
- Create: `content_factory/models.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write schema tests**

Create `tests/test_db.py`:

```python
import sqlite3
import unittest

from content_factory.db import connect, init_db, table_names


class DatabaseTests(unittest.TestCase):
    def test_init_db_creates_required_tables(self):
        conn = connect(":memory:")
        init_db(conn)
        expected = {
            "products",
            "product_facts",
            "product_assets",
            "demand_intakes",
            "benchmark_videos",
            "benchmark_deconstructions",
            "material_assets",
            "content_generations",
            "material_audits",
            "evaluation_reports",
            "ad_performance_logs",
            "reusable_patterns",
        }
        self.assertTrue(expected.issubset(table_names(conn)))

    def test_products_can_be_inserted_with_timestamps(self):
        conn = connect(":memory:")
        init_db(conn)
        conn.execute(
            """
            INSERT INTO products
            (name, product_url, country, category, platform, selling_points, campaign_rules, forbidden_claims, compliance_redlines, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("测试产品", "https://example.com", "巴西", "工具", "TikTok", "快", "首单优惠", "绝对第一", "不得虚构收益", "备注"),
        )
        row = conn.execute("SELECT id, name, created_at, updated_at FROM products").fetchone()
        self.assertEqual(row["name"], "测试产品")
        self.assertIsNotNone(row["created_at"])
        self.assertIsNotNone(row["updated_at"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_db -v`

Expected: FAIL because `content_factory.db` does not exist.

- [ ] **Step 3: Implement schema**

Create `content_factory/models.py`:

```python
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
```

Create `content_factory/db.py` with `connect(path)`, `init_db(conn)`, `table_names(conn)`, `insert_record(conn, table, data)`, `fetch_all(conn, query, params=())`, `fetch_one(conn, query, params=())`, and JSON helpers. The schema must create all tables listed in the spec, use `TEXT` for JSON payload columns, and use `datetime('now')` defaults for timestamps.

- [ ] **Step 4: Run schema tests**

Run: `python3 -m unittest tests.test_db -v`

Expected: PASS.

## Task 3: Mock AI Provider

**Files:**
- Create: `content_factory/ai_provider.py`
- Create: `tests/test_ai_provider.py`

- [ ] **Step 1: Write provider tests**

Create tests proving:
- `structure_demand()` returns platform, country, audience, scenario, goal, duration, outputs, missing_info.
- `audit_materials()` returns `HUMAN_REQUIRED` when required redline materials are missing.
- `audit_materials()` returns `FATAL_FAILED` when the product has compliance redlines and the demand asks for exaggerated claims.
- `generate_content()` returns Chinese scripts for 10/15/30 seconds, storyboard, Runway/HeyGen/ElevenLabs prompts, and Facebook/TikTok copy.
- `evaluate_generation()` returns a 100-point report with the required scoring dimensions.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_ai_provider -v`

Expected: FAIL because provider is missing.

- [ ] **Step 3: Implement `MockAIProvider`**

Implement deterministic Chinese outputs. The provider must not call external APIs and must not read API keys.

- [ ] **Step 4: Run provider tests**

Run: `python3 -m unittest tests.test_ai_provider -v`

Expected: PASS.

## Task 4: Business Services And Pipeline Rules

**Files:**
- Create: `content_factory/services.py`
- Create: `tests/test_services.py`

- [ ] **Step 1: Write service tests**

Create tests for:
- Product creation persists the product.
- Demand intake persists original input and structured JSON.
- Benchmark deconstruction persists both source and decomposition.
- Material creation persists grade, source, compliance, and product link.
- Content generation first creates a material audit.
- `HUMAN_REQUIRED` blocks generation.
- `FATAL_FAILED` blocks generation.
- `PASS` and `AUTO_REPAIR` create content generation plus evaluation report.
- Ad performance input saves metrics and analysis.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_services -v`

Expected: FAIL because `content_factory.services` is missing.

- [ ] **Step 3: Implement service functions**

Implement functions:
- `create_product(conn, data)`
- `add_product_asset(conn, product_id, data)`
- `structure_demand(conn, provider, product_id, raw_input)`
- `deconstruct_benchmark(conn, provider, product_id, data)`
- `create_material(conn, data)`
- `run_material_audit(conn, provider, product_id, demand_id, material_ids)`
- `generate_content(conn, provider, product_id, demand_id, material_ids, benchmark_ids)`
- `record_ad_performance(conn, provider, generation_id, metrics)`

`generate_content` must raise `PipelineBlocked` for `HUMAN_REQUIRED` and `FATAL_FAILED`.

- [ ] **Step 4: Run service tests**

Run: `python3 -m unittest tests.test_services -v`

Expected: PASS.

## Task 5: Server-Rendered UI And HTTP Routes

**Files:**
- Create: `content_factory/views.py`
- Create: `app.py`
- Create: `tests/test_http.py`

- [ ] **Step 1: Write HTTP smoke tests**

Create tests that start the handler against a temporary SQLite database and assert:
- `GET /` returns 200 and contains `海外投流素材内容工厂`.
- `GET /products` returns 200 and contains `产品档案`.
- `POST /products` creates a product and redirects.
- `GET /pipeline` returns 200 and contains `任务工厂`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_http -v`

Expected: FAIL because routes are missing.

- [ ] **Step 3: Implement views**

Build Chinese server-rendered pages:
- Dashboard with counts and recent records.
- Product Archive with product form, list, product detail, and asset upload form.
- Demand/Pipeline page with one-line demand input, structured demand display, material/benchmark selection, generate button, and generation/evaluation output.
- Benchmark page with source input and deconstruction output.
- Material Library with form and list.
- Records page for content generations, audits, and evaluations.
- Ad Performance page with metric form and analysis output.

- [ ] **Step 4: Implement routes**

Routes:
- `GET /`
- `GET /products`
- `POST /products`
- `POST /product-assets`
- `GET /pipeline`
- `POST /demands`
- `POST /generate`
- `GET /benchmarks`
- `POST /benchmarks`
- `GET /materials`
- `POST /materials`
- `GET /records`
- `GET /performance`
- `POST /performance`
- `GET /uploads/<path>`

- [ ] **Step 5: Run HTTP tests**

Run: `python3 -m unittest tests.test_http -v`

Expected: PASS.

## Task 6: README And Manual Verification

**Files:**
- Create: `README.md`
- Modify: `.env.example`

- [ ] **Step 1: Write README**

README must explain:
- What the MVP does.
- Why output is Chinese-only in v1.
- How to configure `.env`.
- How to run database initialization automatically via app startup.
- How to start the app: `python3 app.py`.
- How to run tests: `python3 -m unittest discover -v`.
- Where uploads and SQLite data live.
- How future real AI provider wiring works without hardcoded keys.

- [ ] **Step 2: Run full tests**

Run: `python3 -m unittest discover -v`

Expected: PASS.

- [ ] **Step 3: Start dev server**

Run: `python3 app.py`

Expected: server prints a local URL using configured host and port.

- [ ] **Step 4: Verify in browser**

Open `http://127.0.0.1:8000` and manually verify:
- Product can be created.
- Demand can be structured.
- Missing redline material blocks generation.
- Valid material allows generation.
- Evaluation appears after generation.
- Performance metrics can be saved and analyzed.

## Self-Review

- Spec coverage: Each required page and database table maps to Tasks 2, 4, and 5. Mandatory audit-before-generation and evaluation-after-generation map to Task 4 service tests and implementation. README and no-hardcoded-key requirements map to Tasks 1 and 6.
- Placeholder scan: No `TBD` or `TODO` placeholders are used as implementation requirements. Task 3 and Task 5 intentionally specify behavior-level tests where exact assertions depend on deterministic provider content, and implementation must satisfy the listed outputs.
- Type consistency: Provider method names in this plan use Python snake_case consistently, while the design document used conceptual camelCase names. Service functions call the snake_case provider methods.
