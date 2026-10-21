"""
cc-connect 消息推送通道
将通过 AI 门禁审核的高价值付费工具词，自动推送到飞书聊天窗口。
"""
import glob
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from config import CC_CONNECT_SESSION_KEY

def get_active_feishu_session() -> Tuple[str, Optional[str]]:
    """
    自动从本地 ~/.cc-connect/sessions/ 中发现当前活跃的飞书会话 Key
    返回: (project_name, session_key)
    """
    home = Path.home()
    session_files = glob.glob(str(home / ".cc-connect" / "sessions" / "agy*.json"))
    for sf in session_files:
        try:
            with open(sf, "r", encoding="utf-8") as f:
                data = json.load(f)
                active = data.get("active_session", {})
                for session_key in active.keys():
                    if session_key.startswith("feishu:"):
                        return "agy", session_key
        except Exception:
            pass

    # 兜底会话配置 (优先读取 .env 中配置的 CC_CONNECT_SESSION_KEY)
    if CC_CONNECT_SESSION_KEY:
        return "agy", CC_CONNECT_SESSION_KEY
    return "agy", None

def format_alert_message(item: Dict[str, Any], ai_res: Dict[str, Any]) -> str:
    """
    组装推送到飞书的精简排版消息
    """
    keyword = item.get("keyword", "")
    kind = item.get("kind", "new")
    heat_ratio = item.get("heat_ratio", 0)
    growth_pct = item.get("growth_pct")
    growth_str = f"+{growth_pct}%" if growth_pct else "持续平稳"
    
    brief_what = item.get("brief_what") or (item.get("brief") or {}).get("what") or "暂无说明"
    brief_want = item.get("brief_want") or (item.get("brief") or {}).get("want") or "暂无说明"
    brief_how = item.get("brief_how") or (item.get("brief") or {}).get("how") or "暂无说明"
    
    is_new = (kind == "new")
    kind_tag = "⚡【新词速攻】" if is_new else "💎【二次爆火】"
    tool_category = ai_res.get("tool_category", "在线工具")
    monetization = ai_res.get("monetization", "按次积分包或月费订阅")
    ai_reason = ai_res.get("reason", "符合在线可交互付费工具标准")

    msg = f"""🎯 {kind_tag} 发现高价值付费工具词！

【关键词】: {keyword}
【工具分类】: {tool_category}
【热度指标】: GPTs ×{round(heat_ratio, 2) if heat_ratio else '-'} ｜ 近期涨幅: {growth_str}

📋 这是什么：
{brief_what}

🎯 用户需求：
{brief_want}

🛠️ 哥飞建站与开发建议：
{brief_how}

💰 推荐变现模式：
{monetization}

🤖 AI 审核通过理由：
{ai_reason}
━━━━━━━━━━━━━━━━━━━━
💡 如需开工，直接在飞书回复：
帮我为 {keyword} 生成全套 MVP 落地页与项目脚手架
Antigravity 将直接为你创建项目并写代码！"""
    return msg

def update_keyword_context(item: Dict[str, Any], ai_res: Dict[str, Any]):
    """
    保存最新推送的商机关键词到项目根目录，支持保留最近 N 个推过来的词（应对一次推多张卡片或历史追溯）。
    """
    try:
        workspace_dir = Path(__file__).resolve().parent
        history_json_file = workspace_dir / ".recent_pushed_keywords.json"
        md_file = workspace_dir / "CURRENT_MONITOR_KEYWORD.md"

        recent_list = []
        if history_json_file.exists():
            try:
                recent_list = json.loads(history_json_file.read_text(encoding="utf-8"))
            except Exception:
                recent_list = []

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        heat_ratio = item.get("heat_ratio", 0)
        growth_pct = item.get("growth_pct")
        growth_str = f"+{growth_pct}%" if growth_pct else "平稳"

        record = {
            "keyword": item.get("keyword"),
            "kind": item.get("kind", "new"),
            "category": ai_res.get("tool_category", "工具"),
            "heat_ratio": heat_ratio,
            "growth_pct": growth_pct,
            "growth_str": growth_str,
            "pushed_at": now_str,
            "brief_what": item.get("brief_what") or (item.get("brief") or {}).get("what") or "暂无",
            "brief_want": item.get("brief_want") or (item.get("brief") or {}).get("want") or "暂无",
            "brief_how": item.get("brief_how") or (item.get("brief") or {}).get("how") or "暂无",
            "monetization": ai_res.get("monetization", "积分或订阅"),
            "ai_reason": ai_res.get("reason", "")
        }

        # 过滤掉同名旧记录，将新记录插入最前
        recent_list = [r for r in recent_list if r.get("keyword") != record["keyword"]]
        recent_list.insert(0, record)
        # 保留最近 10 个
        recent_list = recent_list[:10]

        history_json_file.write_text(json.dumps(recent_list, ensure_ascii=False, indent=2), encoding="utf-8")

        # 生成结构化 Markdown 档案，包含最新焦点词与完整历史清单
        latest = recent_list[0]
        md_content = [
            f"# 当前最新商机关键词 (焦点词: {latest['keyword']})",
            f"- **推送时间**: {latest['pushed_at']}",
            f"- **关键词**: {latest['keyword']}",
            f"- **类型**: {'新词速攻' if latest['kind'] == 'new' else '二次爆火'}",
            f"- **工具分类**: {latest['category']}",
            f"- **热度**: GPTs ×{round(latest['heat_ratio'], 2) if latest['heat_ratio'] else '-'} (涨幅: {latest['growth_str']})",
            f"- **这是什么**: {latest['brief_what']}",
            f"- **用户需求**: {latest['brief_want']}",
            f"- **建站建议**: {latest['brief_how']}",
            f"- **推荐变现**: {latest['monetization']}",
            f"- **通过理由**: {latest['ai_reason']}",
            "\n---\n",
            f"## 📋 最近推送的商机列表 (共 {len(recent_list)} 个)",
            "> 💡 用户说“这个词”时默认指第 1 个最新词；用户也可以指定“第 2 个词”或关键词名称进行开发与对比。\n"
        ]

        for idx, r in enumerate(recent_list, start=1):
            tag = "⚡新词速攻" if r.get("kind") == "new" else "💎二次爆火"
            md_content.append(
                f"{idx}. **[{r['keyword']}]** ({tag} | {r.get('category')} | GPTs ×{round(r.get('heat_ratio', 0), 2)})\n"
                f"   - 变现模式: {r.get('monetization')}\n"
                f"   - 建站建议: {r.get('brief_how')[:120]}...\n"
            )

        md_file.write_text("\n".join(md_content), encoding="utf-8")
        print(f"[+] 已更新项目商机上下文 ({len(recent_list)} 个词在库)")
    except Exception as fe:
        print(f"[!] 更新 CURRENT_MONITOR_KEYWORD.md 异常: {fe}")

def send_keyword_alert(item: Dict[str, Any], ai_res: Dict[str, Any]) -> bool:
    """
    通过 cc-connect send CLI 推送卡片/文本
    """
    project, session_key = get_active_feishu_session()
    if not session_key:
        print("[!] 未找到活跃的飞书会话，无法推送。")
        return False

    message_text = format_alert_message(item, ai_res)

    cmd = [
        "cc-connect",
        "send",
        "-p", project,
        "-s", session_key,
        "--stdin"
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=message_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15
        )
        if proc.returncode == 0:
            print(f"[+] 成功通过 cc-connect 推送商机词: {item.get('keyword')}")
            # 同步更新项目根目录上下文文件，确保 agy 收到“做这个词”时具备完整记忆
            update_keyword_context(item, ai_res)
            return True
        else:
            err = proc.stderr.decode("utf-8", errors="ignore")
            print(f"[!] cc-connect send 失败: {err}")
            return False
    except Exception as e:
        print(f"[!] 调用 cc-connect send 异常: {e}")
        return False
