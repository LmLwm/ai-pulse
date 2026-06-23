#!/usr/bin/env python3
"""Generate self-contained index.html with embedded data."""
import json, os, sys, html as h
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetcher import fetch_all

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_good.json")

ICONS = {"Hacker News":"🟠","r/MachineLearning":"🤖","r/LocalLLaMA":"🦙","arXiv cs.AI":"📄",
    "arXiv cs.CL":"📄","GitHub Trending":"⭐","HuggingFace":"🤗","Lobsters":"🦞","36氪":"🇨🇳"}

def _load_cache():
    try:
        with open(CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(cache):
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"   ⚠ 缓存写入失败（不影响本次发布): {e}")

def main():
    print("📡 Fetching data...")
    fresh = fetch_all()
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

    cache = _load_cache()
    data = {}
    stale_since = {}  # name -> 上次成功抓取的时间，本次是回退用的旧数据
    fresh_count = 0
    for name, items in fresh.items():
        ok = bool(items) and "加载失败" not in items[0].get("title", "")
        if ok:
            fresh_count += 1
            data[name] = items
            cache[name] = {"items": items, "ts": now}
        elif name in cache and cache[name].get("items"):
            data[name] = cache[name]["items"]
            stale_since[name] = cache[name].get("ts", "?")
        else:
            data[name] = items  # 没有任何旧数据可用，如实显示失败卡片
    _save_cache(cache)

    total = sum(len(v) for v in data.values())
    active = fresh_count
    print(f"   {active}/{len(data)} sources fresh, {len(stale_since)} using cached fallback, {total} items")

    data_js = json.dumps(data, ensure_ascii=False)

    # Build nav tabs
    nav = '<span class="nt on" data-f="all">📋 全部</span>'
    for name in data:
        icon = ICONS.get(name, "📰")
        nav += f'<span class="nt" data-f="{h.escape(name)}">{icon} {h.escape(name)}</span>'

    # Build stats
    stats = f'<div class="st2"><span class="sn">{active}/{len(data)}</span><span class="sl">源在线</span></div>'
    stats += f'<div class="st2"><span class="sn">{total}</span><span class="sl">条目</span></div>'

    # Build top 5
    scored = []
    for items in data.values():
        for it in items:
            if it.get("score") and "加载失败" not in it.get("title",""):
                scored.append(it)
    scored.sort(key=lambda x: x.get("score",0), reverse=True)
    top5 = scored[:5]
    top_html = '<h3>🔥 热门 Top 5</h3>'
    for i, it in enumerate(top5, 1):
        t = h.escape(it.get("title","")[:60])
        u = h.escape(it.get("url","#"))
        top_html += f'<a href="{u}" target="_blank" class="ti"><span class="tr">#{i}</span><span class="tt">{t}</span><span class="tp">▲{it.get("score",0)}</span></a>'

    # Build sections
    sections = ""
    for name, items in data.items():
        icon = ICONS.get(name, "📰")
        cnt = len(items)
        if name in stale_since:
            dot = f'<span class="sst" title="本次抓取失败，下方为 {h.escape(stale_since[name])} 最后一次成功抓到的数据"></span>'
            stale_tag = f' <span class="stg">缓存于 {h.escape(stale_since[name])}</span>'
        else:
            failed = any("加载失败" in it.get("title","") for it in items) if items else True
            dot = '<span class="sf" title="离线"></span>' if failed else '<span class="so" title="在线"></span>'
            stale_tag = ""
        cards = ""
        for it in items[:25]:
            t = h.escape(it.get("title",""))
            u = h.escape(it.get("url","#"))
            s = h.escape(it.get("summary",""))
            is_err = "加载失败" in it.get("title","")
            cls = "c ec" if is_err else "c"
            meta = []
            if it.get("score"): meta.append(f'<span class="sc">▲ {it["score"]}</span>')
            if it.get("comments"): meta.append(f'<span class="cm">💬 {it["comments"]}</span>')
            if it.get("authors"): meta.append(f'<span class="cm">👤 {h.escape(it["authors"])}</span>')
            if it.get("tags"): meta.append(f'<span class="tg">🏷 {h.escape(it["tags"])}</span>')
            summary_html = f'<p class="sm">{s}</p>' if s else ""
            cards += f'<a href="{u}" target="_blank" rel="noopener" class="{cls}"><div class="ct">{t}</div>{summary_html}<div class="cm2">{" ".join(meta)}</div></a>'
        sections += f'<section class="ss" data-n="{h.escape(name)}"><h2 class="st">{icon} {h.escape(name)} <span class="cn">({cnt})</span>{stale_tag} {dot}</h2><div class="cd">{cards}</div></section>'

    page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Pulse</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<style>
:root{{--bg:#0a0a0f;--s1:#12121a;--s2:#1a1a26;--bd:#2a2a3a;--t1:#e8e8f0;--t2:#8888a0;--a1:#6c5ce7;--a2:#a29bfe;--gn:#00b894;--og:#e17055;--rd:#d63031;--r:12px}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--t1);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",system-ui,sans-serif;line-height:1.6}}
::-webkit-scrollbar{{width:6px}}::-webkit-scrollbar-track{{background:transparent}}::-webkit-scrollbar-thumb{{background:var(--bd);border-radius:3px}}
header{{position:sticky;top:0;z-index:100;background:rgba(10,10,15,.85);backdrop-filter:blur(20px) saturate(180%);border-bottom:1px solid var(--bd);padding:16px 32px;display:flex;align-items:center;justify-content:space-between}}
.logo{{font-size:24px;font-weight:800;background:linear-gradient(135deg,var(--a1),var(--a2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.hr{{display:flex;align-items:center;gap:16px}}
.ut{{color:var(--t2);font-size:13px}}
.sb{{display:flex;gap:24px;padding:16px 32px;background:var(--s1);border-bottom:1px solid var(--bd)}}
.st2{{display:flex;flex-direction:column;align-items:center}}
.sn{{font-size:20px;font-weight:700;color:var(--a2)}}.sl{{font-size:11px;color:var(--t2)}}
.ts{{padding:12px 32px;background:var(--s1);border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:16px;flex-wrap:wrap}}
.ts h3{{font-size:14px;color:var(--t2);white-space:nowrap}}
.ti{{font-size:12px;color:var(--t1);text-decoration:none;background:var(--s2);padding:4px 10px;border-radius:6px;border:1px solid var(--bd);transition:all .2s;display:inline-flex;align-items:center;gap:6px;max-width:320px}}
.ti:hover{{border-color:var(--a1)}}.tr{{color:var(--a2);font-weight:700}}.tt{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.tp{{color:var(--og);font-size:11px;white-space:nowrap}}
.nav{{display:flex;gap:4px;padding:12px 32px;border-bottom:1px solid var(--bd);overflow-x:auto;background:var(--s1)}}
.nt{{padding:8px 16px;border-radius:8px;font-size:13px;font-weight:500;color:var(--t2);cursor:pointer;white-space:nowrap;transition:all .2s;border:1px solid transparent}}
.nt:hover,.nt.on{{color:var(--t1);background:var(--s2);border-color:var(--bd)}}.nt.on{{border-color:var(--a1);color:var(--a2)}}
main{{max-width:1200px;margin:0 auto;padding:24px 32px 64px}}
.ss{{margin-bottom:40px}}
.st{{font-size:18px;font-weight:700;color:var(--t1);margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid var(--bd);display:flex;align-items:center;gap:8px}}
.cn{{font-size:13px;color:var(--t2);font-weight:400}}
.so,.sf,.sst{{width:8px;height:8px;border-radius:50%;display:inline-block;margin-left:auto}}
.so{{background:var(--gn);box-shadow:0 0 6px var(--gn)}}.sf{{background:var(--rd);box-shadow:0 0 6px var(--rd)}}
.sst{{background:#f0a020;box-shadow:0 0 6px #f0a020}}
.stg{{font-size:11px;color:#f0a020;font-weight:400}}
.cd{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}}
.c{{display:block;background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);padding:16px 18px;text-decoration:none;color:inherit;transition:all .2s}}
.c:hover{{background:var(--s2);border-color:var(--a1);transform:translateY(-2px);box-shadow:0 8px 24px rgba(108,92,231,.12)}}
.ec{{opacity:.5;border-color:var(--rd)}}.ec:hover{{transform:none;box-shadow:none}}
.ct{{font-size:14px;font-weight:600;line-height:1.5;color:var(--t1);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.sm{{font-size:12px;color:var(--t2);margin-top:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.cm2{{margin-top:10px;font-size:12px;color:var(--t2);display:flex;gap:12px;align-items:center}}
.sc{{color:var(--og)}}.cm{{color:var(--a2)}}.tg{{color:var(--gn);font-size:11px}}
.ft{{text-align:center;padding:24px;color:var(--t2);font-size:12px;border-top:1px solid var(--bd)}}
@media(max-width:640px){{header{{padding:12px 16px}}.nav{{padding:8px 16px}}main{{padding:16px}}.cd{{grid-template-columns:1fr}}.sb{{padding:12px 16px}}.ts{{padding:8px 16px}}}}
</style>
</head>
<body>
<header><div class="logo">⚡ AI Pulse</div><div class="hr"><span class="ut">更新于 {now}</span></div></header>
<div class="sb">{stats}</div>
<div class="ts">{top_html}</div>
<nav class="nav" id="nv">{nav}</nav>
<main id="main">{sections}</main>
<div class="ft">AI Pulse · 每 2 小时自动更新 · <a href="https://github.com" style="color:var(--a2)">GitHub Pages</a></div>
<script>
document.getElementById("nv").addEventListener("click",function(e){{var t=e.target.closest(".nt");if(!t)return;document.querySelectorAll(".nt").forEach(function(x){{x.classList.remove("on")}});t.classList.add("on");var f=t.dataset.f;document.querySelectorAll(".ss").forEach(function(s){{var n=s.dataset.n||"";s.style.display=f==="all"?"":n.indexOf(f)>=0?"":"none"}})}});
</script>
</body></html>'''

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"✅ Generated {OUT} ({len(page):,} bytes)")

if __name__ == "__main__":
    main()
