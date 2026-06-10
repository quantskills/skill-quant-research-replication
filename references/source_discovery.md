# Source Discovery Rules

Use this reference when the user asks to find a quant paper, search for research reports,
compare candidate papers, or start a replication without providing a PDF/URL.

## Source Classes

1. Academic papers with public APIs:
   - arXiv: best for quantitative finance working papers and preprints.
   - Crossref: best for DOI-indexed journal articles, posted content, and reports.
   - Semantic Scholar: best for broad academic discovery and open-access PDF links.

2. Academic papers without stable open APIs:
   - SSRN, NBER, RePEc/IDEAS, publisher sites, and university repositories.
   - Use targeted web search and record the landing page, PDF URL if available, access date,
     and whether the source is open access, abstract-only, or paywalled.

3. Institutional and broker research reports:
   - Global: AQR, BlackRock, MSCI, S&P Global, Goldman Sachs, JPMorgan, Morgan Stanley,
     and other asset-manager or sell-side research portals.
   - China: Eastmoney report pages/PDF hosts, CICC, CMS, HTSC, CITIC, CNINFO, and other
     public broker or exchange filing/report hosts.
   - Many report portals change frequently or block scraping. Prefer search-result discovery,
     manual URL verification, and user-provided PDFs when direct download is blocked.

## Script

Run:

```bash
python scripts/source_discovery.py "query terms" --preset papers --max 10 --json
python scripts/source_discovery.py "A股 动量 因子 研报" --preset cn_reports --max 10 --json
python scripts/source_discovery.py "factor investing transaction costs" --preset all --max 5 --download-dir /home/coder/project/replication/quant-research-replication/downloads
```

Presets:

- `papers`: arXiv, Crossref, Semantic Scholar, and targeted paper sites.
- `reports`: global institutional and sell-side research report sites.
- `cn_reports`: Chinese public research-report sites and PDF hosts.
- `all`: all of the above.

## Selection Rules

Rank candidate sources by:

1. Relevance to the requested factor, strategy, universe, and market.
2. Availability of the full PDF or complete webpage text.
3. Clear formulas, asset universe, sample period, and portfolio construction rules.
4. Reproducible data requirements.
5. Publication credibility and date.
6. Whether figures/tables can be extracted and audited.

Do not treat a search hit as a source of truth until the PDF/page is opened or downloaded
and its title, author/institution, date, and content are verified.

## Provenance

For each selected source, record in `manifest.json`:

- Search query and source preset/API.
- Result title, URL, PDF URL, source platform, and access date.
- Local downloaded path if any.
- Whether the source is academic paper, institutional report, broker report, blog/web article,
  or user-provided material.
- Any access limitation, paywall, blocked download, OCR issue, or version ambiguity.

## Fallbacks

If automated search fails:

1. Use normal web browsing or search with targeted site queries.
2. Ask the user for a PDF/URL only after trying reasonable public discovery.
3. If a title is known but the PDF is blocked, use the abstract/metadata only for source
   selection and mark replication as blocked until full text is available.
