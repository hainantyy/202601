#!/usr/bin/env python3
"""Simple web crawler.

Features:
- Breadth-first crawl with depth and page limits.
- Optional same-domain restriction.
- Optional robots.txt compliance.
- CSV output with URL, status code, title, depth, and discovered links count.
"""

from __future__ import annotations

import argparse
import csv
import time
from collections import deque
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib import robotparser
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "SimpleCrawler/1.0 (+https://example.local)"


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.in_title = False
        self.title_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            for name, value in attrs:
                if name.lower() == "href" and value:
                    self.links.append(value)
        elif tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_chunks.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(chunk for chunk in self.title_chunks if chunk)


@dataclass
class CrawlRecord:
    url: str
    status: int
    title: str
    depth: int
    links_found: int
    error: str = ""


class Crawler:
    def __init__(
        self,
        start_url: str,
        max_pages: int,
        max_depth: int,
        delay: float,
        same_domain_only: bool,
        obey_robots: bool,
        user_agent: str,
        timeout: int,
    ) -> None:
        self.start_url = normalize_url(start_url)
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.same_domain_only = same_domain_only
        self.obey_robots = obey_robots
        self.user_agent = user_agent
        self.timeout = timeout

        self.start_domain = urlparse(self.start_url).netloc
        self.robot_parser = robotparser.RobotFileParser()
        if obey_robots:
            robots_url = urljoin(self.start_url, "/robots.txt")
            self.robot_parser.set_url(robots_url)
            try:
                self.robot_parser.read()
            except Exception:
                # If robots cannot be fetched, fail open for practicality.
                pass

    def can_fetch(self, url: str) -> bool:
        if self.same_domain_only and urlparse(url).netloc != self.start_domain:
            return False
        if not self.obey_robots:
            return True
        return self.robot_parser.can_fetch(self.user_agent, url)

    def fetch(self, url: str) -> tuple[int, str, list[str], str]:
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                status = getattr(response, "status", 200)
                if "text/html" not in content_type:
                    return status, "", [], ""

                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                parser = LinkExtractor()
                parser.feed(body)
                links = [normalize_url(urljoin(url, link)) for link in parser.links]
                return status, parser.title, links, ""
        except HTTPError as exc:
            return exc.code, "", [], str(exc)
        except URLError as exc:
            return 0, "", [], str(exc)
        except TimeoutError as exc:
            return 0, "", [], str(exc)
        except Exception as exc:
            return 0, "", [], str(exc)

    def crawl(self) -> list[CrawlRecord]:
        queue: deque[tuple[str, int]] = deque([(self.start_url, 0)])
        visited: set[str] = set()
        records: list[CrawlRecord] = []

        while queue and len(records) < self.max_pages:
            url, depth = queue.popleft()
            if url in visited or depth > self.max_depth:
                continue
            visited.add(url)

            if not self.can_fetch(url):
                records.append(CrawlRecord(url=url, status=0, title="", depth=depth, links_found=0, error="blocked"))
                continue

            status, title, links, error = self.fetch(url)
            records.append(
                CrawlRecord(url=url, status=status, title=title, depth=depth, links_found=len(links), error=error)
            )

            if depth < self.max_depth:
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))

            if self.delay > 0:
                time.sleep(self.delay)

        return records


def normalize_url(url: str) -> str:
    cleaned, _fragment = urldefrag(url)
    parsed = urlparse(cleaned)
    if not parsed.scheme:
        cleaned = "https://" + cleaned
    return cleaned.rstrip("/") or cleaned


def write_csv(records: Iterable[CrawlRecord], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "status", "title", "depth", "links_found", "error"])
        for record in records:
            writer.writerow([
                record.url,
                record.status,
                record.title,
                record.depth,
                record.links_found,
                record.error,
            ])


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple website crawler")
    parser.add_argument("start_url", help="Seed URL to begin crawling")
    parser.add_argument("--max-pages", type=int, default=50, help="Maximum number of pages to crawl")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum crawl depth from start URL")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between requests in seconds")
    parser.add_argument("--same-domain-only", action="store_true", help="Crawl only links from the seed domain")
    parser.add_argument("--obey-robots", action="store_true", help="Respect robots.txt rules")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent header")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--output", default="crawl_results.csv", help="Output CSV path")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    crawler = Crawler(
        start_url=args.start_url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        same_domain_only=args.same_domain_only,
        obey_robots=args.obey_robots,
        user_agent=args.user_agent,
        timeout=args.timeout,
    )

    records = crawler.crawl()
    write_csv(records, args.output)
    print(f"Crawled {len(records)} pages. Results saved to: {args.output}")


if __name__ == "__main__":
    main()
