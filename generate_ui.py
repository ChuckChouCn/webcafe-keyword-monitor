import json
import sqlite3
from datetime import datetime
from pathlib import Path
from config import BASE_DIR, DATA_DIR, DB_PATH

def render_sparkline_svg(spark_data, width=100, height=24):
    if not spark_data or not isinstance(spark_data, list) or len(spark_data) < 2:
        return f'<svg width="{width}" height="{height}" class="opacity-20"><line x1="0" y1="{height//2}" x2="{width}" y2="{height//2}" stroke="#f97316" stroke-width="2"/></svg>'
    
    max_val = max(spark_data) if max(spark_data) > 0 else 1
    points = []
    step = width / (len(spark_data) - 1)
    for i, val in enumerate(spark_data):
        x = round(i * step, 1)
        # Invert y because SVG y goes downwards
        y = round(height - 2 - ((val / max_val) * (height - 6)), 1)
        points.append(f"{x},{y}")
    
    points_str = " ".join(points)
    return f'''<svg width="{width}" height="{height}" class="inline-block overflow-visible">
      <polyline fill="none" stroke="#f97316" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="{points_str}" />
    </svg>'''

def generate_dashboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM keywords
        ORDER BY 
            appear_date DESC NULLS LAST,
            burst_date DESC NULLS LAST,
            created_at DESC
    """)
    rows = cur.fetchall()

    keywords_list = []
    count_new_active = 0
    count_resurgence_active = 0
    count_game_active = 0
    count_worth = 0
    count_maybe = 0
    count_skip = 0
    count_paid = 0
    count_all_active = 0

    for r in rows:
        d = dict(r)
        d["verdict_reasons"] = json.loads(d["verdict_reasons"]) if d.get("verdict_reasons") else []
        d["spark"] = json.loads(d["spark"]) if d.get("spark") else []
        d["spark_svg"] = render_sparkline_svg(d["spark"])
        
        kind = d.get("kind")
        category = d.get("category") or "other"
        verdict = d.get("verdict")
        is_skip = (verdict == "skip")

        if not is_skip:
            count_all_active += 1
            if kind == "new":
                count_new_active += 1
            elif kind == "resurgence":
                count_resurgence_active += 1
            if category in ("game", "webgame"):
                count_game_active += 1
        else:
            count_skip += 1

        if verdict == "worth":
            count_worth += 1
        elif verdict == "maybe":
            count_maybe += 1

        if d.get("ai_verdict") == "paid_tool":
            count_paid += 1

        keywords_list.append(d)

    cur.execute("SELECT COUNT(*) FROM batches")
    total_batches = cur.fetchone()[0]
    total_keywords = len(keywords_list)
    conn.close()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keywords_json_str = json.dumps(keywords_list, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>新词发现服务 - 哥飞 1:1 对标看板</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #fbfbfb;
      color: #1e293b;
    }}
    .tag-game {{ background: #e0f2fe; color: #0284c7; }}
    .tag-ai {{ background: #f3e8ff; color: #7e22ce; }}
    .tag-tool {{ background: #e0f2fe; color: #0369a1; }}
    .tag-other {{ background: #f1f5f9; color: #64748b; }}
    .tag-new {{ background: #ffedd5; color: #c2410c; }}
    .tag-rising {{ background: #ecfdf5; color: #047857; }}
    .tag-resurgence {{ background: #fce7f3; color: #be185d; }}
    .tag-recommended {{ background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }}
    .badge-worth {{ background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }}
    .badge-maybe {{ background: #fefce8; color: #a16207; border: 1px solid #fef08a; }}
    .badge-skip {{ background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0; }}
    .badge-paid {{ background: #f0fdf4; color: #166534; border: 1px solid #86efac; }}
  </style>
</head>
<body class="p-4 md:p-8 max-w-6xl mx-auto">
  <!-- 顶栏标题 (1:1 对齐哥飞原版) -->
  <div class="mb-5">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold text-slate-900">新词发现服务</h1>
        <span class="text-xs text-slate-400 font-mono">&lt;/&gt; 本地镜像看板</span>
      </div>
      <div class="flex items-center gap-2">
        <a href="AI与工具_精选付费商机.csv" download class="text-xs px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-medium shadow-sm transition">
          📊 下载精选商机表
        </a>
      </div>
    </div>
    <p class="text-xs text-slate-500 mt-2">
      本地库共收录 <span class="font-semibold text-slate-800">{total_keywords}</span> 个词 · 
      跨 <span class="font-semibold text-slate-800">{total_batches}</span> 个批次 · 
      有效新词 <span class="font-semibold text-orange-600">{count_new_active}</span> 个 · 
      二次爆火 <span class="font-semibold text-pink-600">{count_resurgence_active}</span> 个 · 
      值得做 <span class="font-semibold text-emerald-600">{count_worth}</span> 个
    </p>
    <div class="flex items-center gap-2 mt-2 text-xs text-emerald-600 font-medium">
      <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
      <span>每 10 分钟自动差量同步与 AI 审核 · 最后更新: {now_str}</span>
    </div>
  </div>

  <!-- 分类 Tabs (1:1 对标哥飞网页顶部分类) -->
  <div class="flex flex-wrap items-center gap-1 border-b border-slate-200 pb-2 mb-4 text-sm font-medium">
    <button onclick="setTab('new')" id="tab-new" class="px-3 py-1.5 rounded-lg border-b-2 border-orange-600 text-orange-600 font-bold transition">
      新词 <span class="text-xs opacity-90" id="cnt-new">{count_new_active}</span>
    </button>
    <button onclick="setTab('resurgence')" id="tab-resurgence" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      二次爆火 <span class="text-xs opacity-75">{count_resurgence_active}</span>
    </button>
    <button onclick="setTab('worth')" id="tab-worth" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      🌟 值得做 <span class="text-xs opacity-75">{count_worth}</span>
    </button>
    <button onclick="setTab('paid')" id="tab-paid" class="px-3 py-1.5 rounded-lg text-emerald-700 bg-emerald-50 hover:bg-emerald-100 font-semibold transition">
      🚀 飞书已推 (AI精选) <span class="text-xs opacity-90">{count_paid}</span>
    </button>
    <button onclick="setTab('game')" id="tab-game" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      游戏 <span class="text-xs opacity-75">{count_game_active}</span>
    </button>
    <button onclick="setTab('all')" id="tab-all" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      全部有效 <span class="text-xs opacity-75">{count_all_active}</span>
    </button>
    <button onclick="setTab('skip')" id="tab-skip" class="px-3 py-1.5 rounded-lg text-slate-400 hover:bg-slate-100 transition">
      不值得做 <span class="text-xs opacity-60">{count_skip}</span>
    </button>
  </div>

  <!-- 搜索与筛选控制栏 (1:1 对标哥飞控制栏) -->
  <div class="flex flex-col md:flex-row gap-3 items-center justify-between mb-4 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
    <div class="relative w-full md:w-96">
      <input type="text" id="searchInput" placeholder="搜你站的主词，看它下面能做哪些内页..." oninput="handleSearch()" class="w-full px-3 py-2 pl-9 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:bg-white transition" />
      <span class="absolute left-3 top-2.5 text-slate-400 text-sm">🔍</span>
    </div>

    <div class="flex items-center gap-2 w-full md:w-auto">
      <select id="categoryFilter" onchange="renderCards()" class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none">
        <option value="all" selected>全部方向</option>
        <option value="ai">AI</option>
        <option value="tool">工具</option>
        <option value="game">游戏</option>
        <option value="other">其它</option>
      </select>

      <select id="verdictFilter" onchange="renderCards()" class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none">
        <option value="all" selected>值不值得做 (全部)</option>
        <option value="worth">值得做</option>
        <option value="maybe">可以试试 (可观察)</option>
        <option value="skip">不值得做</option>
      </select>

      <select id="sortBy" onchange="renderCards()" class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none">
        <option value="appear" selected>最新出现 (默认)</option>
        <option value="growth">爆发涨幅排序</option>
        <option value="heat">GPTs 热度倍数排序</option>
      </select>
    </div>
  </div>

  <!-- 列表副标题提示 -->
  <div class="text-xs text-slate-400 mb-3 px-1 flex items-center justify-between">
    <span id="listSubtitle">最近 90 天在谷歌趋势里第一次有量，越新越靠前 · GPTs 倍数 = 近 7 天热度是 GPTs 的多少倍</span>
    <span id="matchCount" class="font-medium text-slate-600">找到 -- 个</span>
  </div>

  <!-- 卡片列表容器 -->
  <div id="cardsContainer" class="space-y-3">
    <!-- 动态卡片 -->
  </div>

  <!-- 无结果提示 -->
  <div id="noResults" class="hidden p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
    没有找到符合条件的关键词
  </div>

  <script>
    const allKeywords = {keywords_json_str};
    let currentTab = 'new'; // 1:1 对齐哥飞线上默认：默认进新词
    let searchQuery = '';

    function setTab(tab) {{
      currentTab = tab;
      document.querySelectorAll('[id^="tab-"]').forEach(el => {{
        el.className = 'px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition';
      }});
      const activeBtn = document.getElementById('tab-' + tab);
      if (activeBtn) {{
        if (tab === 'paid') {{
          activeBtn.className = 'px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold transition';
        }} else {{
          activeBtn.className = 'px-3 py-1.5 rounded-lg border-b-2 border-orange-600 text-orange-600 font-bold transition';
        }}
      }}

      // 调整下拉菜单配合
      if (tab === 'worth') {{
        document.getElementById('verdictFilter').value = 'worth';
      }} else if (tab === 'skip') {{
        document.getElementById('verdictFilter').value = 'skip';
      }} else {{
        document.getElementById('verdictFilter').value = 'all';
      }}
      renderCards();
    }}

    function handleSearch() {{
      searchQuery = document.getElementById('searchInput').value.trim().toLowerCase();
      renderCards();
    }}

    function renderCards() {{
      const container = document.getElementById('cardsContainer');
      const noResults = document.getElementById('noResults');
      const categoryFilter = document.getElementById('categoryFilter').value;
      const verdictFilter = document.getElementById('verdictFilter').value;
      const sortBy = document.getElementById('sortBy').value;

      let filtered = allKeywords.filter(k => {{
        const isSkip = (k.verdict === 'skip');

        // Tab 过滤 (1:1 对标哥飞原版过滤规则)
        if (currentTab === 'new' && (k.kind !== 'new' || isSkip)) return false;
        if (currentTab === 'resurgence' && (k.kind !== 'resurgence' || isSkip)) return false;
        if (currentTab === 'game' && ((k.category !== 'game' && k.category !== 'webgame') || isSkip)) return false;
        if (currentTab === 'worth' && k.verdict !== 'worth') return false;
        if (currentTab === 'paid' && k.ai_verdict !== 'paid_tool') return false;
        if (currentTab === 'skip' && !isSkip) return false;
        if (currentTab === 'all' && isSkip && verdictFilter !== 'skip') return false;

        // 分类下拉过滤
        if (categoryFilter !== 'all') {{
          if (categoryFilter === 'game' && k.category !== 'game' && k.category !== 'webgame') return false;
          if (categoryFilter !== 'game' && k.category !== categoryFilter) return false;
        }}

        // 评级下拉过滤
        if (verdictFilter !== 'all' && k.verdict !== verdictFilter) return false;

        // 搜索过滤
        if (searchQuery) {{
          const matchKw = (k.keyword || '').toLowerCase().includes(searchQuery);
          const matchWhat = (k.brief_what || '').toLowerCase().includes(searchQuery);
          const matchHow = (k.brief_how || '').toLowerCase().includes(searchQuery);
          if (!matchKw && !matchWhat && !matchHow) return false;
        }}
        return true;
      }});

      // 排序
      if (sortBy === 'appear') {{
        filtered.sort((a, b) => (b.appear_date || '').localeCompare(a.appear_date || '') || (b.burst_date || '').localeCompare(a.burst_date || '') || (b.heat_ratio || 0) - (a.heat_ratio || 0));
      }} else if (sortBy === 'growth') {{
        filtered.sort((a, b) => (b.growth_pct || 0) - (a.growth_pct || 0));
      }} else if (sortBy === 'heat') {{
        filtered.sort((a, b) => (b.heat_ratio || 0) - (a.heat_ratio || 0));
      }}

      document.getElementById('matchCount').innerText = `找到 ${{filtered.length}} 个`;

      if (filtered.length === 0) {{
        container.innerHTML = '';
        noResults.classList.remove('hidden');
        return;
      }}
      noResults.classList.add('hidden');

      container.innerHTML = filtered.slice(0, 150).map((k, idx) => {{
        // 分类标签映射
        let catLabel = '其它';
        let catClass = 'tag-other';
        if (k.category === 'game' || k.category === 'webgame') {{
          catLabel = '游戏';
          catClass = 'tag-game';
        }} else if (k.category === 'ai') {{
          catLabel = 'AI';
          catClass = 'tag-ai';
        }} else if (k.category === 'tool') {{
          catLabel = '工具';
          catClass = 'tag-tool';
        }}

        const kindLabel = k.kind === 'new' 
          ? '<span class="px-1.5 py-0.5 rounded text-xs tag-new font-medium">新词</span>' 
          : (k.kind === 'resurgence' ? '<span class="px-1.5 py-0.5 rounded text-xs tag-resurgence font-medium">二次爆火</span>' : '');

        const trendLabel = k.trend_now 
          ? `<span class="px-1.5 py-0.5 rounded text-xs tag-rising font-medium">${{escapeHtml(k.trend_now)}}</span>` 
          : '';

        const pushedLabel = k.pushed_on 
          ? '<span class="px-1.5 py-0.5 rounded text-xs tag-recommended font-medium">推荐过</span>' 
          : '';

        // 日期与起量描述
        const appearShort = k.appear_date ? k.appear_date.substring(5).replace('-', '/') : '';
        const burstShort = k.burst_date ? k.burst_date.substring(5).replace('-', '/') : '';
        let dateLine = `${{appearShort ? appearShort + ' 出现' : ''}} ${{burstShort ? '· ' + burstShort + ' 爆发' : ''}}`;
        if (k.growth_pct) {{
          dateLine += ` · 自身近 7 天 +${{k.growth_pct.toLocaleString()}}%`;
        }} else if (k.appear_date) {{
          dateLine += ` · 自身近 7 天从 0 起量`;
        }}

        // GPTs 倍数
        const heatText = k.heat_ratio !== null && k.heat_ratio !== undefined 
          ? `GPTs <span class="font-bold text-slate-800">×${{k.heat_ratio.toFixed(3)}}</span>` 
          : '-';

        // 评级标签 (对齐哥飞的 [可以试试] / [值得做] / [不值得做])
        let verdictBadge = '';
        if (k.verdict === 'worth') {{
          verdictBadge = `<span class="px-2 py-0.5 rounded text-xs font-semibold badge-worth">值得做</span> <span class="font-semibold text-slate-800">${{escapeHtml(k.verdict_suggestion || '新站首页')}}</span>`;
        }} else if (k.verdict === 'maybe') {{
          verdictBadge = `<span class="px-2 py-0.5 rounded text-xs font-medium badge-maybe">可以试试</span> <span class="text-slate-800 font-medium">${{escapeHtml(k.verdict_suggestion || '做内页')}}</span>`;
        }} else {{
          verdictBadge = `<span class="px-2 py-0.5 rounded text-xs badge-skip">不值得做</span> <span class="text-slate-500">${{escapeHtml(k.verdict_suggestion || '-')}}</span>`;
        }}

        const reasonsStr = (k.verdict_reasons && k.verdict_reasons.length > 0) ? k.verdict_reasons[0] : '';

        // AI 审核横幅
        const isPaid = k.ai_verdict === 'paid_tool';
        const aiBanner = isPaid ? `
          <div class="mt-2.5 p-2.5 bg-emerald-50 rounded-lg border border-emerald-200/90 text-xs text-emerald-950">
            <span class="font-bold text-emerald-700">🚀 飞书已推 · AI 门禁通过:</span>
            <span class="text-emerald-900 ml-1">${{escapeHtml(k.ai_proposal || '符合高价值在线工具变现标准')}}</span>
          </div>
        ` : '';

        return `
          <div class="bg-white rounded-xl border border-slate-200/90 p-5 hover:border-slate-300 shadow-sm transition">
            <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <!-- 左侧信息主区 -->
              <div class="flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-base font-bold text-slate-900 hover:text-orange-600 transition cursor-pointer" onclick="toggleDetails(${{idx}})">
                    ${{escapeHtml(k.keyword)}}
                  </span>
                  <span class="px-1.5 py-0.5 rounded text-xs font-medium ${{catClass}}">${{catLabel}}</span>
                  ${{kindLabel}}
                  ${{trendLabel}}
                  ${{pushedLabel}}
                </div>

                <div class="text-xs text-slate-400 mt-1.5">
                  ${{dateLine}}
                </div>

                <div class="text-xs text-slate-600 mt-2 leading-relaxed">
                  ${{escapeHtml(k.brief_what || '暂无释义')}}
                </div>

                ${{aiBanner}}

                <!-- 哥飞点评条 -->
                <div class="mt-3.5 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  ${{verdictBadge}}
                  ${{reasonsStr ? `<span class="text-slate-500">· ${{escapeHtml(reasonsStr)}}</span>` : ''}}
                </div>

                <!-- 折叠建站指南 -->
                <div id="guide-${{idx}}" class="hidden mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1.5">
                  <div><strong class="text-slate-900">🎯 用户需求:</strong> ${{escapeHtml(k.brief_want || '暂无')}}</div>
                  <div><strong class="text-orange-900">🛠️ 如何做站:</strong> ${{escapeHtml(k.brief_how || '暂无')}}</div>
                  ${{k.page_url ? `<div class="pt-1"><a href="${{k.page_url}}" target="_blank" class="text-orange-600 hover:underline">查看官方详情原帖 ↗</a></div>` : ''}}
                </div>
              </div>

              <!-- 右侧指标与走势图 (1:1 对标哥飞原版) -->
              <div class="flex md:flex-col items-center md:items-end justify-between md:justify-start gap-2 min-w-[200px] border-t md:border-t-0 pt-2 md:pt-0 border-slate-100">
                <div class="text-xs text-slate-600 font-mono">
                  ${{heatText}}
                </div>
                <div class="my-1">
                  ${{k.spark_svg}}
                </div>
                <div class="text-xs text-slate-400 flex items-center gap-3 font-mono">
                  <span>内页候选 <b class="text-slate-600 font-normal">${{k.page_count ?? 0}}</b></span>
                  <span>专门页面 <b class="text-slate-700 font-semibold">${{k.targeted_count ?? 0}}</b></span>
                </div>
              </div>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function toggleDetails(idx) {{
      const el = document.getElementById('guide-' + idx);
      if (el) {{
        el.classList.toggle('hidden');
      }}
    }}

    function escapeHtml(str) {{
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }}

    // 默认进入新词列表
    setTab('new');
  </script>
</body>
</html>
"""

    local_html_path = DATA_DIR / "dashboard.html"
    local_html_path.write_text(html_content, encoding="utf-8")
    print(f"[+] 数据目录看板已更新: {local_html_path.resolve()}")

    try:
        from config import BASE_DIR
        root_html_path = BASE_DIR / "dashboard.html"
        root_html_path.write_text(html_content, encoding="utf-8")
        print(f"[+] 项目根目录看板已更新: {root_html_path.resolve()}")
    except Exception:
        pass

    return local_html_path

if __name__ == "__main__":
    generate_dashboard()
