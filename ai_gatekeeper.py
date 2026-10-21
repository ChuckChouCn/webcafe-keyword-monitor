"""
AI Gatekeeper (AI 门禁审核模块)
严格判定关键词是否为【处于上升红利期、可在线交互、具备明确付费场景（积分/订阅）的工具/软件】。
坚决排除：
1. 游戏、纯娱乐、小说/动漫/影视、新闻八卦、纯内容文章站（只读不交互的百科/攻略/词义查询）。
2. 走势回落、增长为负、已过风口红利期的下行词。
3. 首次出现已在数月前且无近期暴涨的存量旧词。
4. 官方或巨头绝对垄断且毫无第三方截流空间的专有词。
"""
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

SYSTEM_PROMPT = """你是一个专业的出海工具站/微型SaaS投资与孵化专家。
我们的选词把关原则极其严格，必须同时满足以下两项核心标准才允许放行通过：

【标准一：强工具属性与清晰付费场景】
1. 必须是【可在线交互、提供实际功能处理、能让用户掏钱的工具/软件/微型SaaS】（付费模式为按次/算力积分充值包，或月度/年度会员订阅制）。
2. 坚决排除：游戏、纯娱乐、小说/动漫/影视、新闻八卦、纯内容文章站（只读不交互的百科/攻略/词义释义/参数查询）。

【标准二：风口时效与商业可行性】
1. 必须处于【当前热度上升红利期】。
2. 坚决排除：
   - 走势已在“回落/衰退”的词（属于过气凉词，坚决不推）。
   - 首次出现时间早在数月前且无近期暴涨的存量旧词（已经错过风口红利）。
   - 官方或权威垄断且第三方毫无截流/生存空间的品牌专有词。

请评估用户提供的关键词详细指标（包括出现时间、爆发时间、当前走势、涨幅与建站建议）。
请只返回严格合法的 JSON 对象，不要包含 markdown 标记或额外解释，格式严格如下：
{
  "is_paid_tool": true, // 只有同时满足强工具属性 + 处于上升红利期且具备商业可行性时才为 true；若处于下行、过气或无付费场景，务必为 false
  "tool_category": "工具分类 (如: AI生成/开发辅助/数据处理/格式转换/效率工具 等)",
  "monetization": "推荐变现模式 (如: 免费试用1次+额度积分包 或 月付$9.9会员订阅)",
  "reason": "1~2句话说明通过理由（明确收费点与时机优势），或说明淘汰理由（如：已在回落中/过气旧词/游戏类/纯内容无交互/官方垄断等）"
}"""

def evaluate_keyword(item: Dict[str, Any], api_key: str = DEEPSEEK_API_KEY) -> Dict[str, Any]:
    """
    调用大模型对单个关键词进行二元判定与变现模式归纳。
    """
    keyword = item.get("keyword", "")
    kind = item.get("kind", "new")
    category = item.get("category", "")
    heat_ratio = item.get("heat_ratio", 0)
    growth_pct = item.get("growth_pct")
    trend_now = item.get("trend_now", "未知")
    appear_date = item.get("appear_date") or "未知"
    burst_date = item.get("burst_date") or "未知"

    # 优先读取简报详情
    brief_what = item.get("brief_what") or (item.get("brief") or {}).get("what") or "暂无说明"
    brief_want = item.get("brief_want") or (item.get("brief") or {}).get("want") or "暂无说明"
    brief_how = item.get("brief_how") or (item.get("brief") or {}).get("how") or "暂无说明"

    growth_str = f"+{growth_pct}%" if growth_pct is not None and growth_pct > 0 else (f"{growth_pct}%" if growth_pct is not None else "无涨幅数据")

    user_content = f"""关键词：{keyword}
类型定位：{'⚡新词速攻' if kind == 'new' else '💎二次爆火'}
分类：{category}
热度比：GPTs ×{round(heat_ratio, 2) if heat_ratio else '-'}
当前走势：{trend_now} ｜ 近期涨幅：{growth_str}
首次出现时间：{appear_date} ｜ 爆发日期：{burst_date}
这是什么：{brief_what}
用户需求：{brief_want}
建站与开发建议：{brief_how}"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        req = urllib.request.Request(
            DEEPSEEK_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            return {
                "is_paid_tool": bool(result.get("is_paid_tool", False)),
                "tool_category": result.get("tool_category", "工具"),
                "monetization": result.get("monetization", "按次积分或订阅"),
                "reason": result.get("reason", "")
            }
    except Exception as e:
        print(f"[!] AI 审核接口调用异常 ({keyword}): {e}")
        # 降级兜底逻辑：若接口异常，保守返回 False 以免误推垃圾信息
        return {
            "is_paid_tool": False,
            "tool_category": "审核异常",
            "monetization": "未知",
            "reason": f"接口请求失败: {e}"
        }
