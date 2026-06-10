#!/usr/bin/env python3
"""Discover quant papers and research reports from multiple public sources.

Examples:
  python source_discovery.py "momentum futures" --sources arxiv,crossref,semantic,web --max 5
  python source_discovery.py "A股 动量 因子 研报" --preset cn_reports --max 10 --json
  python source_discovery.py "time series momentum" --preset papers --download-dir ./downloads
"""

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape


USER_AGENT = "ReportReplicationSourceDiscovery/1.0 (+local research workflow)"
socket.setdefaulttimeout(6)

PRESETS = {
    "papers": ["arxiv", "crossref", "semantic", "web_papers"],
    "reports": ["web_reports"],
    "cn_reports": ["web_cn_reports"],
    "all": ["arxiv", "crossref", "semantic", "web_papers", "web_reports", "web_cn_reports"],
}

WEB_TARGETS = {
    "web_papers": [
        "site:ssrn.com quantitative finance",
        "site:papers.ssrn.com quantitative finance",
        "site:nber.org finance trading",
        "site:ideas.repec.org finance market",
        "site:academic.oup.com/rfs finance",
        "site:onlinelibrary.wiley.com finance",
    ],
    "web_reports": [
        "site:goldmansachs.com insights quant",
        "site:jpmorgan.com research quant",
        "site:morganstanley.com ideas quant",
        "site:blackrock.com research factor investing",
        "site:aqr.com insights research",
        "site:msci.com research factor investing",
        "site:spglobal.com market intelligence research",
    ],
    "web_cn_reports": [
        "site:pdf.dfcfw.com 量化 研报",
        "site:data.eastmoney.com/report 量化 研报",
        "site:research.cicc.com.cn 量化",
        "site:cmschina.com 量化 研报",
        "site:htsc.com.cn 量化 研报",
        "site:citics.com 量化 研报",
        "site:cninfo.com.cn 量化",
    ],
}


def fetch_text(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def search_arxiv(query, max_results=10):
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    try:
        xml_data = fetch_text(url)
    except Exception as exc:
        return [{"source": "arxiv", "error": str(exc)}]

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_data)
    rows = []
    for entry in root.findall("atom:entry", ns):
        arxiv_id = entry.findtext("atom:id", default="", namespaces=ns).split("/abs/")[-1]
        title = entry.findtext("atom:title", default="", namespaces=ns).strip()
        summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
        published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
        authors = [
            node.findtext("atom:name", default="", namespaces=ns)
            for node in entry.findall("atom:author", ns)
        ]
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "pdf":
                pdf_url = link.get("href") or ""
        rows.append(
            {
                "source": "arxiv",
                "id": arxiv_id,
                "title": " ".join(title.split()),
                "authors": ", ".join([a for a in authors if a][:5]),
                "date": published,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_url,
                "snippet": " ".join(summary.split())[:500],
            }
        )
    return rows


def search_crossref(query, max_results=10):
    params = {
        "query.bibliographic": query,
        "rows": max_results,
        "select": "DOI,title,author,published-print,published-online,URL,type,container-title,abstract",
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(fetch_text(url))
    except Exception as exc:
        return [{"source": "crossref", "error": str(exc)}]

    rows = []
    for item in data.get("message", {}).get("items", []):
        title = " ".join(item.get("title") or [])
        authors = []
        for author in item.get("author", [])[:5]:
            name = " ".join([author.get("given", ""), author.get("family", "")]).strip()
            if name:
                authors.append(name)
        date_parts = (
            item.get("published-online", {}).get("date-parts")
            or item.get("published-print", {}).get("date-parts")
            or [[]]
        )
        date = "-".join(str(x) for x in date_parts[0]) if date_parts and date_parts[0] else ""
        rows.append(
            {
                "source": "crossref",
                "id": item.get("DOI", ""),
                "title": title,
                "authors": ", ".join(authors),
                "date": date,
                "url": item.get("URL", ""),
                "pdf_url": "",
                "snippet": strip_html(item.get("abstract", ""))[:500],
                "type": item.get("type", ""),
                "venue": " ".join(item.get("container-title") or []),
            }
        )
    return rows


def search_semantic_scholar(query, max_results=10):
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,abstract,url,openAccessPdf,venue,externalIds",
    }
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(fetch_text(url))
    except Exception as exc:
        return [{"source": "semantic", "error": str(exc)}]

    rows = []
    for item in data.get("data", []):
        pdf_url = ""
        if isinstance(item.get("openAccessPdf"), dict):
            pdf_url = item["openAccessPdf"].get("url") or ""
        rows.append(
            {
                "source": "semantic",
                "id": item.get("paperId", ""),
                "title": item.get("title", ""),
                "authors": ", ".join(a.get("name", "") for a in item.get("authors", [])[:5]),
                "date": str(item.get("year") or ""),
                "url": item.get("url", ""),
                "pdf_url": pdf_url,
                "snippet": (item.get("abstract") or "")[:500],
                "venue": item.get("venue", ""),
            }
        )
    return rows


def search_web(query, source_name, max_results=10):
    rows = search_duckduckgo(query, source_name, max_results)
    good_rows = [row for row in rows if not row.get("error")]
    if good_rows:
        return rows
    return search_bing(query, source_name, max_results)


def search_duckduckgo(query, source_name, max_results=10):
    params = {"q": query}
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode(params)
    try:
        html = fetch_text(url, timeout=5)
    except Exception as exc:
        return [{"source": source_name, "error": str(exc), "query": query}]

    results = []
    blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    for idx, (href, title_html) in enumerate(blocks[:max_results]):
        url_value = unescape(href)
        if "uddg=" in url_value:
            parsed = urllib.parse.urlparse(url_value)
            qs = urllib.parse.parse_qs(parsed.query)
            url_value = qs.get("uddg", [url_value])[0]
        title = strip_html(title_html)
        snippet = strip_html(snippets[idx]) if idx < len(snippets) else ""
        results.append(
            {
                "source": source_name,
                "id": "",
                "title": title,
                "authors": "",
                "date": "",
                "url": url_value,
                "pdf_url": url_value if ".pdf" in url_value.lower() else "",
                "snippet": snippet[:500],
                "query": query,
            }
        )
    return results


def search_bing(query, source_name, max_results=10):
    params = {"q": query}
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(params)
    try:
        html = fetch_text(url, timeout=5)
    except Exception as exc:
        return [{"source": source_name, "error": str(exc), "query": query}]

    results = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', html, re.S)
    for block in blocks[:max_results]:
        link = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        snippet = re.search(r'<p>(.*?)</p>', block, re.S)
        url_value = unescape(link.group(1))
        title = strip_html(link.group(2))
        results.append(
            {
                "source": source_name,
                "id": "",
                "title": title,
                "authors": "",
                "date": "",
                "url": url_value,
                "pdf_url": url_value if ".pdf" in url_value.lower() else "",
                "snippet": strip_html(snippet.group(1))[:500] if snippet else "",
                "query": query,
            }
        )
    return results


def strip_html(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(unescape(value).split())


def expand_sources(args):
    if args.preset:
        return PRESETS[args.preset]
    return [s.strip() for s in args.sources.split(",") if s.strip()]


def discover(query, sources, max_results):
    all_rows = []
    for source in sources:
        if source == "arxiv":
            rows = search_arxiv(query, max_results)
        elif source == "crossref":
            rows = search_crossref(query, max_results)
        elif source == "semantic":
            rows = search_semantic_scholar(query, max_results)
        elif source in WEB_TARGETS:
            rows = []
            targets = WEB_TARGETS[source][: max(1, min(len(WEB_TARGETS[source]), max_results))]
            per_target = max(1, max_results // max(1, len(targets)) + 1)
            for target in targets:
                rows.extend(search_web(f"{query} {target}", source, per_target))
                if len([r for r in rows if not r.get("error")]) >= max_results:
                    break
                time.sleep(0.5)
            rows = rows[:max_results]
        else:
            rows = [{"source": source, "error": f"unknown source: {source}"}]
        all_rows.extend(rows)
        time.sleep(0.5)
    return dedupe(all_rows)


def dedupe(rows):
    seen = set()
    output = []
    for row in rows:
        key = (row.get("url") or row.get("pdf_url") or row.get("title") or "").lower()
        key = re.sub(r"\W+", "", key)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def download_pdfs(rows, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for row in rows:
        pdf_url = row.get("pdf_url") or ""
        if not pdf_url:
            continue
        name = row.get("id") or row.get("title") or "paper"
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")[:120] or "paper"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        path = os.path.join(output_dir, name)
        if os.path.exists(path):
            row["download_path"] = path
            continue
        try:
            req = urllib.request.Request(pdf_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as response, open(path, "wb") as fh:
                fh.write(response.read())
            row["download_path"] = path
        except Exception as exc:
            row["download_error"] = str(exc)
    return rows


def print_table(rows):
    for idx, row in enumerate(rows, 1):
        print(f"[{idx}] {row.get('title') or '(untitled)'}")
        print(f"    source: {row.get('source', '')}")
        if row.get("authors"):
            print(f"    authors: {row['authors']}")
        if row.get("date"):
            print(f"    date: {row['date']}")
        print(f"    url: {row.get('url', '')}")
        if row.get("pdf_url"):
            print(f"    pdf: {row['pdf_url']}")
        if row.get("snippet"):
            print(f"    note: {row['snippet']}")
        if row.get("error"):
            print(f"    error: {row['error']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Search quant papers and research reports")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--sources", default="arxiv,crossref,semantic", help="Comma-separated sources")
    parser.add_argument("--preset", choices=sorted(PRESETS), help="Source preset")
    parser.add_argument("--max", type=int, default=10, help="Max results per source")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", help="Write results to JSON file")
    parser.add_argument("--download-dir", help="Download direct/open-access PDFs into this directory")
    args = parser.parse_args()

    sources = expand_sources(args)
    rows = discover(args.query, sources, args.max)
    if args.download_dir:
        rows = download_pdfs(rows, args.download_dir)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_table(rows)

    if not rows:
        sys.exit(1)


if __name__ == "__main__":
    main()
