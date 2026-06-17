#!/usr/bin/env python3
"""AI Pulse — data fetcher for GitHub Actions. Stdlib only."""

import json
import re
import socket
import ssl
import threading
import time
import urllib.request
import urllib.error
from xml.etree import ElementTree as ET

# Force IPv4 to avoid connectivity issues on some hosts
_orig_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_gai(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_gai
socket.setdefaulttimeout(15)
CTX = ssl.create_default_context()

def _get(url, timeout=12, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 AI-Pulse/2.0"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()

def _json(url, **kw):
    return json.loads(_get(url, **kw))

def _safe(fn, name, retries=1):
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if i < retries:
                time.sleep(1)
            else:
                return [{"title": f"⚠ {name} 加载失败: {type(e).__name__}", "source": name, "url": "#", "link": "#"}]

def fetch_hn(limit=20):
    ids = _json("https://hacker-news.firebaseio.com/v0/topstories.json")[:limit]
    results = [None] * len(ids)
    def _one(i, sid):
        try:
            s = _json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=6)
            results[i] = {"title": s.get("title",""), "url": s.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": s.get("score",0), "comments": s.get("descendants",0), "source": "Hacker News",
                "link": f"https://news.ycombinator.com/item?id={sid}"}
        except: pass
    ts = [threading.Thread(target=_one, args=(i,s), daemon=True) for i,s in enumerate(ids)]
    for t in ts: t.start()
    for t in ts: t.join(10)
    return [r for r in results if r]

def fetch_reddit(sub, limit=25):
    for endpoint in [f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}&raw_json=1",
                     f"https://old.reddit.com/r/{sub}/hot.json?limit={limit}&raw_json=1"]:
        try:
            data = _json(endpoint, headers={"User-Agent": "AI-Pulse/2.0 (github-pages; python)"})
            break
        except Exception:
            continue
    else:
        raise Exception("All Reddit endpoints failed")
    return [{"title": p["data"]["title"], "url": p["data"].get("url",""), "score": p["data"].get("score",0),
        "comments": p["data"].get("num_comments",0), "source": f"r/{sub}",
        "link": f"https://reddit.com{p['data'].get('permalink','')}"}
        for p in data.get("data",{}).get("children",[]) if not p["data"].get("stickied")]

def fetch_arxiv(query, limit=15):
    raw = _get(f"https://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={limit}", timeout=15).decode("utf-8", errors="replace")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(raw)
    items = []
    for e in root.findall("a:entry", ns):
        title = (e.findtext("a:title","",ns) or "").strip().replace("\n"," ")
        summary = (e.findtext("a:summary","",ns) or "").strip()[:200]
        link_el = e.find("a:link[@rel='alternate']",ns)
        link = link_el.get("href","") if link_el is not None else ""
        authors = [a.findtext("a:name","",ns) for a in e.findall("a:author",ns)]
        items.append({"title": title, "url": link, "summary": summary, "authors": ", ".join(authors[:3]), "source": "arXiv", "link": link})
    return items

def fetch_github(limit=20):
    raw = _get("https://github.com/trending?since=daily", timeout=15).decode("utf-8", errors="replace")
    items = []
    for m in re.finditer(r'<h2 class="h3[^"]*">\s*<a[^>]*href="(/[^"]+)"', raw):
        path = m.group(1).strip()
        if "/sponsors" in path or path.count("/") != 2:
            continue
        after = raw[m.end():m.end()+800]
        desc_m = re.search(r'<p class="[^"]*col-9[^"]*">([^<]+)</p>', after)
        if not desc_m:
            desc_m = re.search(r'<p class="[^"]*">([^<]{10,})</p>', after)
        desc = desc_m.group(1).strip() if desc_m else ""
        items.append({"title": path.lstrip("/"), "url": f"https://github.com{path}",
            "summary": desc, "source": "GitHub Trending", "link": f"https://github.com{path}"})
        if len(items) >= limit: break
    return items

def fetch_hf(limit=15):
    data = _json(f"https://huggingface.co/api/models?sort=trending&direction=-1&limit={limit}")
    return [{"title": m.get("id",""), "url": f"https://huggingface.co/{m.get('id','')}",
        "summary": f"👍 {m.get('likes',0):,} · ⬇ {m.get('downloads',0):,}", "source": "HuggingFace",
        "link": f"https://huggingface.co/{m.get('id','')}"} for m in data]

def fetch_lobsters(limit=15):
    data = _json("https://lobste.rs/hottest.json")
    return [{"title": s.get("title",""), "url": s.get("url") or s.get("comments_url",""),
        "score": s.get("score",0), "comments": s.get("comment_count",0), "source": "Lobsters",
        "link": s.get("comments_url",""), "tags": ", ".join(s.get("tags",[]))} for s in data[:limit]]

def fetch_36kr(limit=15):
    raw = _get("https://36kr.com/feed", timeout=12).decode("utf-8", errors="replace")
    root = ET.fromstring(raw)
    kws = ["ai","人工智能","大模型","gpt","llm","智能","机器学习","深度学习","claude","gemini","openai","自动驾驶","具身智能","机器人","agent"]
    items = []
    for it in root.iter("item"):
        title = it.findtext("title","")
        link = it.findtext("link","")
        desc = (it.findtext("description","") or "")[:200]
        if any(k in (title+desc).lower() for k in kws):
            items.append({"title": title, "url": link, "summary": desc, "source": "36氪", "link": link})
            if len(items) >= limit: break
    return items

SOURCES = [
    ("Hacker News",     lambda: _safe(fetch_hn, "Hacker News")),
    ("r/MachineLearning", lambda: _safe(lambda: fetch_reddit("MachineLearning"), "r/MachineLearning")),
    ("r/LocalLLaMA",    lambda: _safe(lambda: fetch_reddit("LocalLLaMA"), "r/LocalLLaMA")),
    ("arXiv cs.AI",     lambda: _safe(lambda: fetch_arxiv("cat:cs.AI"), "arXiv cs.AI")),
    ("arXiv cs.CL",     lambda: _safe(lambda: fetch_arxiv("cat:cs.CL"), "arXiv cs.CL")),
    ("GitHub Trending", lambda: _safe(fetch_github, "GitHub Trending")),
    ("HuggingFace",     lambda: _safe(fetch_hf, "HuggingFace")),
    ("Lobsters",        lambda: _safe(fetch_lobsters, "Lobsters")),
    ("36氪",            lambda: _safe(fetch_36kr, "36氪")),
]

def fetch_all():
    results = {}
    lock = threading.Lock()
    done = threading.Event()
    total = len(SOURCES)
    def _run(name, fn):
        try: d = fn()
        except Exception as e: d = [{"title": f"⚠ {name}: {e}", "source": name, "url": "#", "link": "#"}]
        with lock:
            results[name] = d
            if len(results) >= total: done.set()
    for name, fn in SOURCES:
        threading.Thread(target=_run, args=(name, fn), daemon=True).start()
    done.wait(timeout=60)
    return results
