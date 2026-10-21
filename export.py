import csv
import json
import sqlite3
from pathlib import Path
from config import DATA_DIR, DB_PATH

def _export_query_to_csv(conn, query: str, output_path: Path):
    """
    导出 SQL 查询结果为 UTF-8-SIG 编码的 CSV 文件。
    优先尝试 pandas（若已安装），否则使用标准库 csv。
    """
    try:
        import pandas as pd
        df = pd.read_sql_query(query, conn)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return len(df)
    except ImportError:
        cur = conn.cursor()
        cur.execute(query)
        headers = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return len(rows)

def export_all():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. 导出 AI 与 工具类【值得做】高潜付费词 (Excel 友好 utf-8-sig)
    query_ai_tool = """
    SELECT 
        keyword as '关键词',
        category as '分类(AI/Tool)',
        CASE WHEN kind = 'new' THEN '⚡ 新词(速攻卖积分)' ELSE '💎 二次爆火(做长线订阅)' END as '推荐变现策略',
        growth_pct as '涨幅(%)',
        trend_now as '当前走势',
        heat_ratio as '相对热度(GPTs倍数)',
        verdict_suggestion as '建议做站形态',
        appear_date as '首次出现日期',
        brief_what as '这是什么产品/模型',
        brief_want as '用户痛点与搜索意图',
        brief_how as '怎么做工具/收积分指南',
        page_url as '详情链接'
    FROM keywords
    WHERE verdict = 'worth' AND category IN ('ai', 'tool')
    ORDER BY 
        CASE WHEN kind = 'resurgence' THEN 1 ELSE 2 END,
        heat_ratio DESC
    """
    worth_csv_path = DATA_DIR / "AI与工具_精选付费商机.csv"
    count_ai_tool = _export_query_to_csv(conn, query_ai_tool, worth_csv_path)
    print(f"[+] 已导出 AI与工具付费商机表: {worth_csv_path.resolve()} (共 {count_ai_tool} 条)")

    # 2. 导出全量词库
    query_all = """
    SELECT 
        keyword as '关键词',
        verdict as '评级',
        category as '分类',
        growth_pct as '涨幅(%)',
        trend_now as '当前走势',
        heat_ratio as '相对热度比',
        verdict_suggestion as '建议做站形态',
        appear_date as '首次出现日期',
        burst_date as '爆发日期',
        brief_what as '这是什么',
        brief_want as '搜索用户需求',
        brief_how as '如何做站',
        page_url as '详情链接'
    FROM keywords
    ORDER BY 
        CASE WHEN verdict = 'worth' THEN 1 WHEN verdict = 'maybe' THEN 2 ELSE 3 END,
        growth_pct DESC NULLS LAST
    """
    all_csv_path = DATA_DIR / "全部新词库_全量.csv"
    count_all = _export_query_to_csv(conn, query_all, all_csv_path)
    print(f"[+] 已导出全量 CSV: {all_csv_path.resolve()} (共 {count_all} 条)")

    # 3. 提取所有 worth 和 maybe 数据用于生成交互式 HTML 看板
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM keywords
        WHERE verdict IN ('worth', 'maybe')
        ORDER BY 
            CASE WHEN verdict = 'worth' THEN 1 ELSE 2 END,
            growth_pct DESC NULLS LAST
    """)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    
    items = []
    for r in rows:
        item = dict(zip(columns, r))
        item["verdict_reasons"] = json.loads(item["verdict_reasons"]) if item.get("verdict_reasons") else []
        item["spark"] = json.loads(item["spark"]) if item.get("spark") else []
        items.append(item)

    conn.close()
    return worth_csv_path, all_csv_path, items

if __name__ == "__main__":
    export_all()
