import json
import os
import sqlite3


def connect(path):
    if path != ":memory:":
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def dumps_json(value):
    return json.dumps(value, ensure_ascii=False)


def loads_json(value, default=None):
    if value in (None, ""):
        return default
    return json.loads(value)


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            product_url TEXT,
            country TEXT,
            category TEXT,
            platform TEXT,
            selling_points TEXT,
            campaign_rules TEXT,
            forbidden_claims TEXT,
            compliance_redlines TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS product_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            fact_key TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS product_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            file_path TEXT,
            external_url TEXT,
            original_name TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS demand_intakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            raw_input TEXT NOT NULL,
            structured_json TEXT NOT NULL,
            missing_info TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS benchmark_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            source_type TEXT NOT NULL,
            source_url TEXT,
            screenshot_path TEXT,
            script_text TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS benchmark_deconstructions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_id INTEGER NOT NULL REFERENCES benchmark_videos(id) ON DELETE CASCADE,
            deconstruction_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS material_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            material_type TEXT,
            source TEXT,
            scenario TEXT,
            grade TEXT NOT NULL,
            reusable INTEGER NOT NULL DEFAULT 0,
            compliant INTEGER NOT NULL DEFAULT 1,
            file_path TEXT,
            external_url TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS material_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            demand_id INTEGER NOT NULL REFERENCES demand_intakes(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            audit_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS content_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            demand_id INTEGER NOT NULL REFERENCES demand_intakes(id) ON DELETE CASCADE,
            audit_id INTEGER NOT NULL REFERENCES material_audits(id) ON DELETE CASCADE,
            generation_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS evaluation_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_id INTEGER NOT NULL REFERENCES content_generations(id) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            report_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ad_performance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_id INTEGER NOT NULL REFERENCES content_generations(id) ON DELETE CASCADE,
            spend REAL DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            cpm REAL DEFAULT 0,
            link_clicks INTEGER DEFAULT 0,
            ctr REAL DEFAULT 0,
            registrations INTEGER DEFAULT 0,
            recharges INTEGER DEFAULT 0,
            cpa REAL DEFAULT 0,
            play_3s INTEGER DEFAULT 0,
            play_50 INTEGER DEFAULT 0,
            play_95 INTEGER DEFAULT 0,
            play_100 INTEGER DEFAULT 0,
            analysis_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS performance_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT NOT NULL UNIQUE,
            report_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reusable_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id INTEGER,
            title TEXT NOT NULL,
            pattern_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()


def table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def insert_record(conn, table, data):
    keys = list(data.keys())
    placeholders = ", ".join("?" for _ in keys)
    columns = ", ".join(keys)
    values = [data[key] for key in keys]
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cursor.lastrowid


def fetch_one(conn, query, params=()):
    return conn.execute(query, params).fetchone()


def fetch_all(conn, query, params=()):
    return conn.execute(query, params).fetchall()
