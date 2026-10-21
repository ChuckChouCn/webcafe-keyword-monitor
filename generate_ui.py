import json
import sqlite3
from pathlib import Path
from config import DATA_DIR, DB_PATH

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

    # Query all records, default ordered by appear_date desc, burst_date desc
    cur.execute("""
        SELECT * FROM keywords
        ORDER BY 
            appear_date DESC NULLS LAST,
            burst_date DESC NULLS LAST,
            updated_at DESC
    """)
    rows = cur.fetchall()

    keywords_list = []
    count_new = 0
    count_resurgence = 0
    count_worth = 0
    count_skip = 0

    for r in rows:
        d = dict(r)
        d["verdict_reasons"] = json.loads(d["verdict_reasons"]) if d.get("verdict_reasons") else []
        d["spark"] = json.loads(d["spark"]) if d.get("spark") else []
        d["spark_svg"] = render_sparkline_svg(d["spark"])
        
        kind = d.get("kind")
        if kind == "new":
            count_new += 1
        elif kind == "resurgence":
            count_resurgence += 1
        
        verdict = d.get("verdict")
        if verdict == "worth":
            count_worth += 1
        elif verdict == "skip":
            count_skip += 1

        keywords_list.append(d)

    cur.execute("SELECT COUNT(*) FROM batches")
    total_batches = cur.fetchone()[0]
    total_keywords = len(keywords_list)

    conn.close()

    keywords_json_str = json.dumps(keywords_list, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>新词发现服务 - 哥飞对标看板</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #fbfbfb;
      color: #1e293b;
    }}
    .tag-game {{ background: #e0f2fe; color: #0284c7; }}
    .tag-ai {{ background: #ede9fe; color: #7c3aed; }}
    .tag-tool {{ background: #fef3c7; color: #d97706; }}
    .tag-other {{ background: #f1f5f9; color: #64748b; }}
    .tag-new {{ background: #ffedd5; color: #ea580c; }}
    .tag-rising {{ background: #dcfce7; color: #16a34a; }}
    .tag-resurgence {{ background: #fce7f3; color: #db2777; }}
    .badge-worth {{ background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }}
    .badge-maybe {{ background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }}
    .badge-skip {{ background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0; }}
  </style>
</head>
<body class="p-4 md:p-8 max-w-6xl mx-auto">
  <!-- 顶栏标题 -->
  <div class="mb-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold text-slate-900">新词发现服务</h1>
        <span class="text-xs px-2 py-0.5 bg-slate-100 text-slate-500 rounded font-mono">&lt;/&gt; 本地私有镜像</span>
      </div>
      <div class="flex items-center gap-2">
        <a href="精选高价值新词_值得做.csv" download class="text-xs px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-medium shadow-sm transition">
          📊 下载 Excel 值得做词表 ({count_worth})
        </a>
      </div>
    </div>
    <p class="text-xs text-slate-500 mt-2">
      本地库共收录 <span class="font-semibold text-slate-800">{total_keywords}</span> 个词 · 
      新词 <span class="font-semibold text-orange-600">{count_new}</span> 个 · 
      二次爆火 <span class="font-semibold text-pink-600">{count_resurgence}</span> 个 · 
      值得做 <span class="font-semibold text-emerald-600">{count_worth}</span> 个
    </p>
    <div class="flex items-center gap-2 mt-2 text-xs text-emerald-600 font-medium">
      <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
      <span>每天自动差量同步 · 跨 {total_batches} 个采集批次 · 永久本地保存无需担心 VIP 过期</span>
    </div>
  </div>

  <!-- 分类 Tabs (对标哥飞网页) -->
  <div class="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3 mb-4 text-sm font-medium">
    <button onclick="setTab('new')" id="tab-new" class="px-3 py-1.5 rounded-lg bg-slate-900 text-white transition">
      新词 <span class="text-xs opacity-80" id="cnt-new">{count_new}</span>
    </button>
    <button onclick="setTab('resurgence')" id="tab-resurgence" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      二次爆火 <span class="text-xs opacity-70">{count_resurgence}</span>
    </button>
    <button onclick="setTab('worth')" id="tab-worth" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      🌟 值得做 <span class="text-xs opacity-70">{count_worth}</span>
    </button>
    <button onclick="setTab('game')" id="tab-game" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      游戏
    </button>
    <button onclick="setTab('ai')" id="tab-ai" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      AI
    </button>
    <button onclick="setTab('tool')" id="tab-tool" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      工具
    </button>
    <button onclick="setTab('all')" id="tab-all" class="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition">
      全部 <span class="text-xs opacity-70">{total_keywords}</span>
    </button>
  </div>

  <!-- 搜索与筛选控制栏 -->
  <div class="flex flex-col md:flex-row gap-3 items-center justify-between mb-4 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
    <div class="relative w-full md:w-96">
      <input type="text" id="searchInput" placeholder="搜你站的主词，看它下面能做哪些内页..." oninput="handleSearch()" class="w-full px-3 py-2 pl-9 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:bg-white transition" />
      <span class="absolute left-3 top-2.5 text-slate-400 text-sm">🔍</span>
    </div>

    <div class="flex items-center gap-2 w-full md:w-auto">
      <select id="verdictFilter" onchange="renderCards()" class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none">
        <option value="all">值不值得做 (全部)</option>
        <option value="worth" selected>仅看：值得做 (Worth)</option>
        <option value="maybe">仅看：可观察 (Maybe)</option>
        <option value="skip">仅看：不值得做 (Skip)</option>
      </select>

      <select id="sortBy" onchange="renderCards()" class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none">
        <option value="appear">最新出现 (推荐)</option>
        <option value="growth">爆发涨幅排序</option>
        <option value="heat">GPTs 热度倍数排序</option>
      </select>
    </div>
  </div>

  <!-- 副标题提示 -->
  <div class="text-xs text-slate-400 mb-3 px-1 flex items-center justify-between">
    <span id="listSubtitle">最近 90 天在谷歌趋势里第一次有量，越新越靠前 · GPTs 倍数 = 近 7 天热度是 GPTs 的多少倍</span>
    <span id="matchCount" class="font-medium text-slate-600">找到 -- 个</span>
  </div>

  <!-- 卡片列表容器 (对标哥飞网页的信息流卡片布局) -->
  <div id="cardsContainer" class="space-y-3">
    <!-- 动态卡片 -->
  </div>

  <!-- 无结果提示 -->
  <div id="noResults" class="hidden p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
    没有找到符合条件的关键词
  </div>

  <script>
    const allKeywords = {keywords_json_str};
    let currentTab = 'worth'; // 默认进入精选值得做
    let searchQuery = '';

    function setTab(tab) {{
      currentTab = tab;
      document.querySelectorAll('[id^="tab-"]').forEach(el => {{
        el.className = 'px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 transition';
      }});
      const activeBtn = document.getElementById('tab-' + tab);
      if (activeBtn) activeBtn.className = 'px-3 py-1.5 rounded-lg bg-slate-900 text-white transition';

      // 调整下拉菜单配合
      if (tab === 'worth') {{
        document.getElementById('verdictFilter').value = 'worth';
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
      const verdictFilter = document.getElementById('verdictFilter').value;
      const sortBy = document.getElementById('sortBy').value;

      let filtered = allKeywords.filter(k => {{
        // Tab 过滤
        if (currentTab === 'new' && k.kind !== 'new') return false;
        if (currentTab === 'resurgence' && k.kind !== 'resurgence') return false;
        if (currentTab === 'game' && k.category !== 'game' && k.category !== 'webgame') return false;
        if (currentTab === 'ai' && k.category !== 'ai') return false;
        if (currentTab === 'tool' && k.category !== 'tool') return false;
        if (currentTab === 'worth' && k.verdict !== 'worth') return false;

        // 下拉评级过滤
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
        filtered.sort((a, b) => (b.appear_date || '').localeCompare(a.appear_date || '') || (b.burst_date || '').localeCompare(a.burst_date || ''));
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

      container.innerHTML = filtered.slice(0, 100).map((k, idx) => {{
        // 分类标签
        const catClass = k.category === 'game' || k.category === 'webgame' ? 'tag-game' : (k.category === 'ai' ? 'tag-ai' : (k.category === 'tool' ? 'tag-tool' : 'tag-other'));
        const kindLabel = k.kind === 'new' ? '<span class="px-1.5 py-0.5 rounded text-xs tag-new font-medium">新词</span>' : (k.kind === 'resurgence' ? '<span class="px-1.5 py-0.5 rounded text-xs tag-resurgence font-medium">二次爆火</span>' : '');
        const trendLabel = k.trend_now ? `<span class="px-1.5 py-0.5 rounded text-xs tag-rising font-medium">${{escapeHtml(k.trend_now)}}</span>` : '';

        // 日期
        const appearShort = k.appear_date ? k.appear_date.substring(5).replace('-', '/') : '';
        const burstShort = k.burst_date ? k.burst_date.substring(5).replace('-', '/') : '';
        const dateLine = `${{appearShort ? appearShort + ' 出现' : ''}} ${{burstShort ? '· ' + burstShort + ' 爆发' : ''}} ${{k.growth_pct ? '· 近期涨幅 +' + k.growth_pct.toLocaleString() + '%' : ''}}`;

        // GPTs 倍数
        const heatText = k.heat_ratio !== null && k.heat_ratio !== undefined ? `GPTs <span class="font-bold text-slate-800">×${{k.heat_ratio.toFixed(k.heat_ratio < 1 ? 3 : 2)}}</span>` : '-';

        // 评级高亮条
        const isWorth = k.verdict === 'worth';
        const isMaybe = k.verdict === 'maybe';
        const verdictBadge = isWorth
          ? `<span class="px-2 py-0.5 rounded text-xs font-semibold badge-worth">值得做</span> <span class="font-semibold text-slate-800">${{escapeHtml(k.verdict_suggestion || '新站首页')}}</span>`
          : (isMaybe ? `<span class="px-2 py-0.5 rounded text-xs font-medium badge-maybe">可观察</span> <span class="text-slate-700">${{escapeHtml(k.verdict_suggestion || '-')}}</span>` : `<span class="px-2 py-0.5 rounded text-xs badge-skip">不值得做</span>`);

        const reasonsStr = (k.verdict_reasons && k.verdict_reasons.length > 0) ? k.verdict_reasons[0] : '';

        return `
          <div class="bg-white rounded-xl border border-slate-200/90 p-5 hover:border-slate-300 shadow-sm transition">
            <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <!-- 左侧信息主区 -->
              <div class="flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-base font-bold text-slate-900 hover:text-indigo-600 transition cursor-pointer" onclick="toggleDetails(${{idx}})">
                    ${{escapeHtml(k.keyword)}}
                  </span>
                  <span class="px-1.5 py-0.5 rounded text-xs font-medium ${{catClass}}">${{escapeHtml(k.category || 'other')}}</span>
                  ${{kindLabel}}
                  ${{trendLabel}}
                </div>

                <div class="text-xs text-slate-400 mt-1.5">
                  ${{dateLine}}
                </div>

                <div class="text-xs text-slate-600 mt-2 leading-relaxed">
                  ${{escapeHtml(k.brief_what || '暂无释义')}}
                </div>

                <!-- 哥飞点评条 -->
                <div class="mt-3.5 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  ${{verdictBadge}}
                  ${{reasonsStr ? `<span class="text-slate-500">· ${{escapeHtml(reasonsStr)}}</span>` : ''}}
                </div>

                <!-- 折叠的详细建站指南 (点击关键词展开) -->
                <div id="guide-${{idx}}" class="hidden mt-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1.5">
                  <div><strong class="text-slate-900">🎯 用户需求:</strong> ${{escapeHtml(k.brief_want || '暂无')}}</div>
                  <div><strong class="text-indigo-900">🛠️ 如何做站:</strong> ${{escapeHtml(k.brief_how || '暂无')}}</div>
                  ${{k.page_url ? `<div class="pt-1"><a href="${{k.page_url}}" target="_blank" class="text-indigo-600 hover:underline">查看官方详情原帖 ↗</a></div>` : ''}}
                </div>
              </div>

              <!-- 右侧指标与走势图 (完全对标哥飞网页) -->
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

    // 初始化渲染
    setTab('worth');
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

if __name__ == "__main__":
    generate_dashboard()
