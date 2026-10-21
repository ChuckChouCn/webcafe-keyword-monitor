import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            finished_at TEXT,
            keyword_count INTEGER,
            page_url TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            keyword TEXT PRIMARY KEY,
            category TEXT,
            kind TEXT,
            trend_now TEXT,
            heat_ratio REAL,
            growth_pct INTEGER,
            appear_date TEXT,
            burst_date TEXT,
            pushed_on TEXT,
            page_count INTEGER,
            targeted_count INTEGER,
            verdict TEXT,
            verdict_reasons TEXT,
            verdict_suggestion TEXT,
            brief_what TEXT,
            brief_want TEXT,
            brief_how TEXT,
            sources TEXT,
            spark TEXT,
            page_url TEXT,
            first_batch_id TEXT,
            last_batch_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            batch_id TEXT,
            trend_now TEXT,
            heat_ratio REAL,
            growth_pct INTEGER,
            verdict TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Indexes for fast querying
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kw_verdict ON keywords(verdict);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kw_category ON keywords(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kw_growth ON keywords(growth_pct);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kw_pushed_on ON keywords(pushed_on);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kw_created ON keywords(created_at);")
    conn.close()

def is_batch_fetched(batch_id: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM batches WHERE id = ?", (batch_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def save_batch_and_keywords(batch_data: Dict[str, Any], keywords: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Saves batch metadata and upserts keywords.
    Returns counts: {'new_keywords': int, 'updated_keywords': int, 'worth_count': int}
    """
    conn = get_connection()
    new_kw_count = 0
    updated_kw_count = 0
    worth_count = 0
    now = datetime.now().isoformat()

    with conn:
        # Save batch
        conn.execute("""
            INSERT OR REPLACE INTO batches (id, finished_at, keyword_count, page_url, fetched_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            batch_data.get("id"),
            batch_data.get("finished_at"),
            batch_data.get("keyword_count", len(keywords)),
            batch_data.get("page_url"),
            now
        ))

        batch_id = batch_data.get("id")

        for kw in keywords:
            keyword_name = kw.get("keyword", "").strip()
            if not keyword_name:
                continue

            verdict = kw.get("verdict") or ""
            if verdict == "worth":
                worth_count += 1

            growth_pct = kw.get("growth_pct")
            heat_ratio = kw.get("heat_ratio")
            trend_now = kw.get("trend_now")
            category = kw.get("category")
            kind = kw.get("kind")
            appear_date = kw.get("appear_date")
            burst_date = kw.get("burst_date")
            pushed_on = kw.get("pushed_on")
            page_count = kw.get("page_count")
            targeted_count = kw.get("targeted_count")
            verdict_suggestion = kw.get("verdict_suggestion")

            verdict_reasons_json = json.dumps(kw.get("verdict_reasons", []), ensure_ascii=False)
            sources_json = json.dumps(kw.get("sources", []), ensure_ascii=False)
            spark_json = json.dumps(kw.get("spark", []), ensure_ascii=False)

            brief = kw.get("brief") or {}
            brief_what = brief.get("what", "")
            brief_want = brief.get("want", "")
            brief_how = brief.get("how", "")
            page_url = kw.get("page_url", "")

            # Check existing
            cur = conn.cursor()
            cur.execute("SELECT first_batch_id FROM keywords WHERE keyword = ?", (keyword_name,))
            existing = cur.fetchone()

            if existing:
                updated_kw_count += 1
                conn.execute("""
                    UPDATE keywords SET
                        category = ?, kind = ?, trend_now = ?, heat_ratio = ?, growth_pct = ?,
                        appear_date = ?, burst_date = ?, pushed_on = ?, page_count = ?, targeted_count = ?,
                        verdict = ?, verdict_reasons = ?, verdict_suggestion = ?,
                        brief_what = ?, brief_want = ?, brief_how = ?, sources = ?, spark = ?,
                        page_url = ?, last_batch_id = ?, updated_at = ?
                    WHERE keyword = ?
                """, (
                    category, kind, trend_now, heat_ratio, growth_pct,
                    appear_date, burst_date, pushed_on, page_count, targeted_count,
                    verdict, verdict_reasons_json, verdict_suggestion,
                    brief_what, brief_want, brief_how, sources_json, spark_json,
                    page_url, batch_id, now, keyword_name
                ))
            else:
                new_kw_count += 1
                conn.execute("""
                    INSERT INTO keywords (
                        keyword, category, kind, trend_now, heat_ratio, growth_pct,
                        appear_date, burst_date, pushed_on, page_count, targeted_count,
                        verdict, verdict_reasons, verdict_suggestion,
                        brief_what, brief_want, brief_how, sources, spark,
                        page_url, first_batch_id, last_batch_id, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                """, (
                    keyword_name, category, kind, trend_now, heat_ratio, growth_pct,
                    appear_date, burst_date, pushed_on, page_count, targeted_count,
                    verdict, verdict_reasons_json, verdict_suggestion,
                    brief_what, brief_want, brief_how, sources_json, spark_json,
                    page_url, batch_id, batch_id, now, now
                ))

            # Record snapshot for history
            conn.execute("""
                INSERT INTO keyword_snapshots (keyword, batch_id, trend_now, heat_ratio, growth_pct, verdict, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (keyword_name, batch_id, trend_now, heat_ratio, growth_pct, verdict, now))

    conn.close()
    return {
        "new_keywords": new_kw_count,
        "updated_keywords": updated_kw_count,
        "worth_count": worth_count
    }
