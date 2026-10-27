#!/usr/bin/env python3
"""Lightweight scheduled health checks for AREBATOP's published SEO basics.

This checks availability and on-page technical signals. It does NOT measure
Google rankings or confirm Google indexing; those require Search Console data.
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import os
import xml.etree.ElementTree as ET

BASE = "https://arebatop.github.io/arebatop-site/"
SITEMAP_URL = BASE + "sitemap.xml"
ROBOTS_URL = BASE + "robots.txt"
TIMEOUT = 20

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.title_text = []
        self.h1_count = 0
        self.meta_description = ""
        self.canonical = ""
        self.robots = ""
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta" and attrs.get("name", "").lower() == "description":
            self.meta_description = attrs.get("content", "").strip()
        elif tag == "meta" and attrs.get("name", "").lower() == "robots":
            self.robots = attrs.get("content", "").strip()
        elif tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonical = attrs.get("href", "").strip()
    def handle_endtag(self, tag):
        if tag == "title":
            self.title = False
    def handle_data(self, data):
        if self.title:
            self.title_text.append(data.strip())

def fetch(url):
    req = Request(url, headers={"User-Agent": "AREBATOP-SEO-HealthCheck/1.0"})
    with urlopen(req, timeout=TIMEOUT) as response:
        return response.status, response.read().decode("utf-8", errors="replace")

issues = []
report = []
try:
    status, robots = fetch(ROBOTS_URL)
    report.append(f"- robots.txt: HTTP {status}")
    if "Sitemap: " + SITEMAP_URL not in robots:
        issues.append("robots.txt does not point to the expected sitemap URL")
except Exception as e:
    robots = ""
    issues.append(f"robots.txt fetch failed: {e}")

try:
    status, sitemap = fetch(SITEMAP_URL)
    root = ET.fromstring(sitemap)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text.strip() for node in root.findall(".//sm:loc", ns) if node.text]
    report.append(f"- sitemap.xml: HTTP {status}; {len(urls)} URLs listed")
    if not urls:
        issues.append("sitemap contains no URLs")
    if any(not url.startswith(BASE) for url in urls):
        issues.append("sitemap contains a URL outside the expected site")
except Exception as e:
    urls = []
    issues.append(f"sitemap fetch/parse failed: {e}")

for url in urls:
    try:
        status, html = fetch(url)
        parser = MetaParser()
        parser.feed(html)
        title = " ".join(parser.title_text).strip()
        label = url.removeprefix(BASE)
        if label == "":
            label = "homepage"
        checks = []
        if status != 200:
            issues.append(f"{label}: HTTP {status}")
        if not title:
            issues.append(f"{label}: missing title")
        if not parser.meta_description:
            issues.append(f"{label}: missing meta description")
        if not parser.canonical:
            issues.append(f"{label}: missing canonical")
        if parser.robots and ("noindex" in parser.robots.lower()):
            issues.append(f"{label}: robots meta contains noindex")
        if parser.h1_count == 0:
            issues.append(f"{label}: missing H1")
        report.append(f"- {label}: HTTP {status}; title={'OK' if title else 'MISSING'}; description={'OK' if parser.meta_description else 'MISSING'}; canonical={'OK' if parser.canonical else 'MISSING'}; H1 count={parser.h1_count}")
    except HTTPError as e:
        issues.append(f"{url}: HTTP {e.code}")
        report.append(f"- {url}: HTTP {e.code}")
    except (URLError, TimeoutError, Exception) as e:
        issues.append(f"{url}: fetch/check failed: {e}")
        report.append(f"- {url}: ERROR {e}")

summary = ["## AREBATOP — SEO technical health check", "", *report, "", "### Findings"]
summary += [f"- ⚠️ {item}" for item in issues] if issues else ["- No issues detected by these basic checks."]
summary += ["", "_Limit: this audit checks published pages and technical SEO basics. It does not query Google Search Console, confirm indexing, or measure rankings._", ""]
summary_text = "\n".join(summary)
print(summary_text)
summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(summary_text)
if issues:
    raise SystemExit(1)
