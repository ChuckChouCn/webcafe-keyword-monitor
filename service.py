import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from db import get_connection, init_db, is_batch_fetched, save_batch_and_keywords
from api_client import WebCafeAPIClient

class KeywordMonitorService:
    def __init__(self, api_client: Optional[WebCafeAPIClient] = None):
        init_db()
        self.client = api_client or WebCafeAPIClient()

    def sync(self, max_pages: int = 1, force: bool = False) -> Dict[str, Any]:
        """
        Sync keyword batches from WebCafe API.
        Only fetches new batches that haven't been stored yet, unless force=True.
        """
        batches_fetched = 0
        batches_skipped = 0
        total_new_keywords = 0
        total_updated_keywords = 0
        all_new_worth_keywords = []

        for page in range(1, max_pages + 1):
            batch_list_resp = self.client.get_keyword_batches(page=page)
            data = batch_list_resp.get("data", {})
            batches = data.get("batches", [])
            has_more = data.get("has_more", False)

            if not batches:
                break

            for b in batches:
                batch_id = b.get("id")
                if not force and is_batch_fetched(batch_id):
                    batches_skipped += 1
                    continue

                # Fetch detailed batch data
                batch_detail = self.client.get_batch_details(batch_id)
                detail_data = batch_detail.get("data", {})
                batch_meta = detail_data.get("batch", b)
                keywords = detail_data.get("keywords", [])

                save_res = save_batch_and_keywords(batch_meta, keywords)
                batches_fetched += 1
                total_new_keywords += save_res["new_keywords"]
                total_updated_keywords += save_res["updated_keywords"]

                # Extract worth keywords from this batch
                worth_items = [k for k in keywords if k.get("verdict") == "worth"]
                all_new_worth_keywords.extend(worth_items)

            if not has_more:
                break

        return {
            "batches_fetched": batches_fetched,
            "batches_skipped": batches_skipped,
            "new_keywords": total_new_keywords,
            "updated_keywords": total_updated_keywords,
            "new_worth_keywords": all_new_worth_keywords
        }

    def list_keywords(
        self,
        verdict: Optional[str] = None,
        category: Optional[str] = None,
        min_growth: Optional[int] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query keywords with multiple filter criteria."""
        conn = get_connection()
        cur = conn.cursor()

        conditions = []
        params = []

        if verdict:
            conditions.append("verdict = ?")
            params.append(verdict)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if min_growth is not None:
            conditions.append("growth_pct >= ?")
            params.append(min_growth)
        if query:
            conditions.append("keyword LIKE ?")
            params.append(f"%{query}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT * FROM keywords
            {where_clause}
            ORDER BY
                CASE WHEN verdict = 'worth' THEN 1 WHEN verdict = 'maybe' THEN 2 ELSE 3 END,
                growth_pct DESC NULLS LAST,
                updated_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cur.execute(sql, params)
        rows = cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["verdict_reasons"] = json.loads(d["verdict_reasons"]) if d.get("verdict_reasons") else []
            d["sources"] = json.loads(d["sources"]) if d.get("sources") else []
            d["spark"] = json.loads(d["spark"]) if d.get("spark") else []
            results.append(d)

        conn.close()
        return results

    def get_keyword(self, keyword_name: str) -> Optional[Dict[str, Any]]:
        """Get complete details and history for a specific keyword."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM keywords WHERE keyword = ?", (keyword_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None

        kw_data = dict(row)
        kw_data["verdict_reasons"] = json.loads(kw_data["verdict_reasons"]) if kw_data.get("verdict_reasons") else []
        kw_data["sources"] = json.loads(kw_data["sources"]) if kw_data.get("sources") else []
        kw_data["spark"] = json.loads(kw_data["spark"]) if kw_data.get("spark") else []

        # Get snapshots
        cur.execute("SELECT * FROM keyword_snapshots WHERE keyword = ? ORDER BY recorded_at DESC", (keyword_name,))
        kw_data["history"] = [dict(r) for r in cur.fetchall()]
        conn.close()
        return kw_data

    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics of the database."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM batches")
        total_batches = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM keywords")
        total_keywords = cur.fetchone()[0]

        cur.execute("SELECT verdict, COUNT(*) FROM keywords GROUP BY verdict")
        verdict_counts = dict(cur.fetchall())

        cur.execute("SELECT category, COUNT(*) FROM keywords GROUP BY category ORDER BY COUNT(*) DESC LIMIT 8")
        category_counts = dict(cur.fetchall())

        cur.execute("SELECT id, finished_at, keyword_count FROM batches ORDER BY id DESC LIMIT 1")
        latest_batch = cur.fetchone()

        conn.close()
        return {
            "total_batches": total_batches,
            "total_keywords": total_keywords,
            "verdicts": verdict_counts,
            "top_categories": category_counts,
            "latest_batch": dict(latest_batch) if latest_batch else None
        }

    def generate_markdown_report(self, hours: int = 24, limit: int = 30) -> str:
        """Generate an actionable Markdown report of recently discovered/updated high-value keywords."""
        conn = get_connection()
        cur = conn.cursor()

        time_threshold = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cur.execute("""
            SELECT * FROM keywords
            WHERE verdict IN ('worth', 'maybe') AND updated_at >= ?
            ORDER BY
                CASE WHEN verdict = 'worth' THEN 1 ELSE 2 END,
                growth_pct DESC NULLS LAST
            LIMIT ?
        """, (time_threshold, limit))

        rows = cur.fetchall()
        conn.close()

        stats = self.get_statistics()
        lines = [
            f"# 哥飞新词发现与监控简报",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 统计范围: 最近 {hours} 小时\n",
            f"### 📊 数据概览",
            f"- **收录总批次**: {stats['total_batches']} 个",
            f"- **入库关键词**: {stats['total_keywords']} 个",
            f"- **评级分布**: `worth (值得做)`: {stats['verdicts'].get('worth', 0)} 个 | `maybe (可观察)`: {stats['verdicts'].get('maybe', 0)} 个 | `skip (跳过)`: {stats['verdicts'].get('skip', 0)} 个",
            f"- **最新批次**: `{stats['latest_batch']['id'] if stats['latest_batch'] else '无'}` ({stats['latest_batch']['finished_at'] if stats['latest_batch'] else ''})\n",
            f"---",
            f"### 🚀 精选高价值新词 (Worth & Maybe)\n"
        ]

        if not rows:
            lines.append("当前时间段内暂无更新的 `worth` 或 `maybe` 词。建议运行 `sync` 同步更多历史或最新批次。")
            return "\n".join(lines)

        for idx, r in enumerate(rows, 1):
            kw = dict(r)
            reasons = json.loads(kw["verdict_reasons"]) if kw.get("verdict_reasons") else []
            growth_str = f"+{kw['growth_pct']}%" if kw.get("growth_pct") else "平稳"
            heat_str = f"{round(kw['heat_ratio']*100, 1)}% GPTs" if kw.get("heat_ratio") else "-"

            verdict_badge = "🌟 **【值得做 WORTH】**" if kw["verdict"] == "worth" else "👀 **【可观察 MAYBE】**"

            lines.append(f"#### {idx}. `{kw['keyword']}` {verdict_badge}")
            lines.append(f"- **分类**: `{kw['category']}` | **涨幅**: `{growth_str}` | **热度**: `{heat_str}` | **走势**: `{kw['trend_now'] or '-'}`")
            lines.append(f"- **建议形态**: `{kw['verdict_suggestion'] or '新站首页'}` | **首次发现**: `{kw['appear_date'] or '-'}` | **爆发日期**: `{kw['burst_date'] or '-'}`")
            
            if reasons:
                lines.append(f"- **推荐理由 (为什么值得做)**:")
                for r_item in reasons:
                    lines.append(f"  * {r_item}")

            if kw.get("brief_what") or kw.get("brief_want") or kw.get("brief_how"):
                lines.append(f"- **建站行动指南**:")
                if kw.get("brief_what"):
                    lines.append(f"  * **这是什么**: {kw['brief_what']}")
                if kw.get("brief_want"):
                    lines.append(f"  * **用户需求**: {kw['brief_want']}")
                if kw.get("brief_how"):
                    lines.append(f"  * **如何做站**: {kw['brief_how']}")

            if kw.get("page_url"):
                lines.append(f"- **官方分析详情**: [{kw['page_url']}]({kw['page_url']})")

            lines.append("")

        return "\n".join(lines)
