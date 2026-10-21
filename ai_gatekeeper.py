"""
AI Gatekeeper (AI 门禁审核模块)
严格判定关键词是否为【可在线交互、具备明确付费场景（积分/订阅）的工具/软件】。
坚决排除：游戏、纯娱乐、小说/动漫/影视、新闻八卦、纯内容文章站（只读不交互的百科/攻略/词义查询）。
"""
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

SYSTEM_PROMPT = """你是一个专业的出海工具站/微型SaaS投资与孵化专家。
我们的原则非常明确：
1. 绝对不碰游戏、纯娱乐、小说/动漫/影视、新闻八卦、纯内容文章站（只读不交互的百科/攻略/词义释义）。
2. 只做【可在线交互、提供实际功能、能让用户掏钱的工具/软件】（付费模式为购买计算/生成积分包，或月度/年度订阅制）。

请评估用户提供的关键词及哥飞建站策略。
请只返回严格合法的 JSON 对象，不要包含 markdown 标记或额外解释，格式严格如下：
{
  "is_paid_tool": true, // 必须严格：只有当它确实能做成让用户在线输入并处理输出的工具软件，且具备明确收费场景时为 true
  "tool_category": "工具类型 (如: AI视频生成/图片设计处理/格式转换/数据查询/计算器/开发辅助 等)",
  "monetization": "推荐变现模式 (如: 免费试玩1~2次+积分充值包 或 月付$9.9会员订阅)",
  "reason": "1~2句话说明为什么认为它能收钱，或者为什么淘汰（命中游戏/纯资讯/无付费场景等）"
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

    # 优先读取简报详情
    brief_what = item.get("brief_what") or (item.get("brief") or {}).get("what") or "暂无说明"
    brief_want = item.get("brief_want") or (item.get("brief") or {}).get("want") or "暂无说明"
    brief_how = item.get("brief_how") or (item.get("brief") or {}).get("how") or "暂无说明"

    user_content = f"""关键词：{keyword}
类型：{'新词速攻' if kind == 'new' else '二次爆火'}
分类：{category}
热度：GPTs ×{round(heat_ratio, 2) if heat_ratio else '-'} ｜ 涨幅：{growth_pct}%
这是什么：{brief_what}
用户需求：{brief_want}
建站建议：{brief_how}"""

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
