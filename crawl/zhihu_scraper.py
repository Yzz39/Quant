#!/usr/bin/env python3
"""Rate-limited exporter for publicly accessible Zhihu question answers."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


API_ROOT = "https://www.zhihu.com/api/v4"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
ANSWER_INCLUDE = (
    "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,"
    "collapse_reason,comment_count,content,voteup_count,created_time,"
    "updated_time,question,excerpt;data[*].author.follower_count,"
    "badge[*].topics"
)
QUESTION_ID_RE = re.compile(r"(?:^|/)question/(\d+)(?:/|$)")


class ScraperError(RuntimeError):
    """Expected error that should be shown without a traceback."""


class _AnswerHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "p",
        "pre",
        "section",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.image_urls: list[str] = []
        self.links: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        attr_map = dict(attrs)
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")
        if tag == "img":
            image_url = (
                attr_map.get("data-original")
                or attr_map.get("data-actualsrc")
                or attr_map.get("src")
            )
            if image_url:
                self.image_urls.append(image_url)
            alt = attr_map.get("alt")
            if alt:
                self.parts.append(f"[{alt}]")
        if tag == "a" and attr_map.get("href"):
            self.links.append(attr_map["href"] or "")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if not self._ignored_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _unique_http_urls(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        absolute = urljoin("https://www.zhihu.com", value.strip())
        if urlparse(absolute).scheme not in {"http", "https"}:
            continue
        if absolute not in seen:
            result.append(absolute)
            seen.add(absolute)
    return result


def html_to_text_and_assets(html: str | None) -> tuple[str, list[str], list[str]]:
    parser = _AnswerHTMLParser()
    parser.feed(html or "")
    raw_text = "".join(parser.parts).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in raw_text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, _unique_http_urls(parser.image_urls), _unique_http_urls(parser.links)


def parse_question_id(value: str) -> str:
    candidate = value.strip()
    if candidate.isdigit():
        return candidate
    match = QUESTION_ID_RE.search(urlparse(candidate).path)
    if match:
        return match.group(1)
    raise argparse.ArgumentTypeError(
        f"Cannot find a Zhihu question ID in {value!r}; use a numeric ID or question URL."
    )


def _iso_utc(unix_timestamp: Any) -> str | None:
    if unix_timestamp in {None, ""}:
        return None
    try:
        value = float(unix_timestamp)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_answer(answer: dict[str, Any], fallback_question_id: str) -> dict[str, Any]:
    answer_id = str(answer.get("id") or "").strip()
    if not answer_id:
        raise ScraperError("Zhihu returned an answer without an ID.")

    question = answer.get("question") if isinstance(answer.get("question"), dict) else {}
    question_id = str(question.get("id") or fallback_question_id)
    author = answer.get("author") if isinstance(answer.get("author"), dict) else {}
    content_text, image_urls, outgoing_links = html_to_text_and_assets(answer.get("content"))
    excerpt_text, _, _ = html_to_text_and_assets(answer.get("excerpt"))
    canonical_url = f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"

    return {
        "schema_version": 1,
        "answer_id": answer_id,
        "question_id": question_id,
        "question_title": question.get("title") or "",
        "author_id": str(author.get("id") or ""),
        "author_name": author.get("name") or "",
        "author_url_token": author.get("url_token") or "",
        "author_headline": author.get("headline") or "",
        "voteup_count": int(answer.get("voteup_count") or 0),
        "comment_count": int(answer.get("comment_count") or 0),
        "created_time": answer.get("created_time"),
        "created_at": _iso_utc(answer.get("created_time")),
        "updated_time": answer.get("updated_time"),
        "updated_at": _iso_utc(answer.get("updated_time")),
        "is_collapsed": bool(answer.get("is_collapsed", False)),
        "collapse_reason": answer.get("collapse_reason") or "",
        "excerpt": excerpt_text,
        "content_text": content_text,
        "image_urls": image_urls,
        "outgoing_links": outgoing_links,
        "url": canonical_url,
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def load_cookie_header(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        value = path.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        raise ScraperError(f"Cannot read cookie file {path}: {exc}") from exc
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    if "\n" in value or "\r" in value:
        raise ScraperError("Cookie file must contain one raw Cookie header line.")
    if not value:
        raise ScraperError(f"Cookie file is empty: {path}")
    return value


def load_existing_answer_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    answer_ids: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ScraperError(
                    f"Cannot resume: {path}:{line_number} is not valid JSONL."
                ) from exc
            answer_id = str(item.get("answer_id") or "")
            if answer_id:
                answer_ids.add(answer_id)
    return answer_ids


def _retry_after_seconds(error: HTTPError, attempt: int) -> float:
    raw_value = error.headers.get("Retry-After")
    if raw_value:
        try:
            return min(120.0, max(0.0, float(raw_value)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(raw_value)
                now = datetime.now(retry_at.tzinfo or timezone.utc)
                return min(120.0, max(0.0, (retry_at - now).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(120.0, 2.0**attempt)


@dataclass
class ZhihuClient:
    cookie: str | None = None
    timeout: float = 30.0
    retries: int = 3

    def get_json(self, url: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Referer": "https://www.zhihu.com/",
            "User-Agent": USER_AGENT,
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        for attempt in range(self.retries + 1):
            try:
                with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    payload = json.loads(response.read().decode(charset))
                    if not isinstance(payload, dict):
                        raise ScraperError("Zhihu returned an unexpected JSON response.")
                    return payload
            except HTTPError as exc:
                if exc.code in {401, 403}:
                    raise ScraperError(
                        f"Zhihu returned HTTP {exc.code}. The page may require your own valid "
                        "session; refresh the cookie or open the page manually. Do not bypass "
                        "CAPTCHA or access controls."
                    ) from exc
                if exc.code == 429 or 500 <= exc.code < 600:
                    if attempt < self.retries:
                        wait_seconds = _retry_after_seconds(exc, attempt + 1)
                        print(
                            f"HTTP {exc.code}; retrying in {wait_seconds:.1f}s "
                            f"({attempt + 1}/{self.retries})...",
                            file=sys.stderr,
                        )
                        time.sleep(wait_seconds)
                        continue
                raise ScraperError(f"Zhihu request failed with HTTP {exc.code}.") from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.retries:
                    wait_seconds = min(30.0, 2.0 ** (attempt + 1))
                    print(
                        f"Network error; retrying in {wait_seconds:.1f}s "
                        f"({attempt + 1}/{self.retries})...",
                        file=sys.stderr,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise ScraperError(f"Zhihu request failed: {exc}") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ScraperError("Zhihu returned a response that is not valid JSON.") from exc

        raise ScraperError("Zhihu request exhausted all retries.")

    def answer_page(
        self, question_id: str, *, offset: int, limit: int, sort_by: str
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "include": ANSWER_INCLUDE,
                "limit": limit,
                "offset": offset,
                "platform": "desktop",
                "sort_by": sort_by,
            }
        )
        return self.get_json(f"{API_ROOT}/questions/{question_id}/answers?{query}")


def scrape_question(
    client: ZhihuClient,
    question_id: str,
    output_handle: Any,
    existing_ids: set[str],
    *,
    max_answers: int,
    page_size: int,
    delay: float,
    sort_by: str,
) -> tuple[int, int]:
    fetched = 0
    written = 0
    offset = 0

    while max_answers == 0 or fetched < max_answers:
        requested_limit = page_size
        if max_answers:
            requested_limit = min(page_size, max_answers - fetched)
        payload = client.answer_page(
            question_id, offset=offset, limit=requested_limit, sort_by=sort_by
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise ScraperError("Zhihu response is missing the answer data list.")
        if not data:
            break

        for raw_answer in data:
            if not isinstance(raw_answer, dict):
                continue
            fetched += 1
            normalized = normalize_answer(raw_answer, question_id)
            if normalized["answer_id"] in existing_ids:
                continue
            output_handle.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            output_handle.flush()
            existing_ids.add(normalized["answer_id"])
            written += 1

        paging = payload.get("paging") if isinstance(payload.get("paging"), dict) else {}
        if paging.get("is_end") is True or len(data) < requested_limit:
            break
        offset += len(data)
        if max_answers == 0 or fetched < max_answers:
            time.sleep(delay)

    return fetched, written


def resolve_output_path(output: Path | None, question_ids: Iterable[str]) -> Path:
    if output is not None:
        return output
    unique_question_ids = list(dict.fromkeys(question_ids))
    if len(unique_question_ids) != 1:
        raise ValueError("--output is required when scraping multiple questions")
    return Path("crawl") / f"{unique_question_ids[0]}zhihu_answer.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export publicly accessible Zhihu answers to UTF-8 JSONL."
    )
    parser.add_argument(
        "questions",
        nargs="+",
        type=parse_question_id,
        metavar="QUESTION",
        help="numeric question ID or https://www.zhihu.com/question/... URL",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSONL destination (default: crawl/<question_id>zhihu_answer.json)",
    )
    parser.add_argument(
        "--cookie-file",
        type=Path,
        default=Path("crawl/cookie.txt"),
        help="UTF-8 file containing your own raw Cookie header "
        "(default: crawl/cookie.txt)",
    )
    parser.add_argument(
        "--max-answers",
        type=int,
        default=0,
        help="maximum answers per question; 0 fetches all (default: 0)",
    )
    parser.add_argument("--page-size", type=int, default=20, choices=range(1, 21))
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between pages")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--sort-by", choices=("default", "updated"), default="default"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the output instead of resuming and deduplicating",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.output = resolve_output_path(args.output, args.questions)
    except ValueError as exc:
        parser.error(str(exc))
    if args.max_answers < 0:
        parser.error("--max-answers must be >= 0")
    if args.delay < 1.0:
        parser.error("--delay must be >= 1.0 second")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.retries < 0:
        parser.error("--retries must be >= 0")

    temporary_output: Path | None = None
    try:
        cookie = load_cookie_header(args.cookie_file)
        existing_ids = set() if args.overwrite else load_existing_answer_ids(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        client = ZhihuClient(cookie=cookie, timeout=args.timeout, retries=args.retries)
        use_atomic_output = args.overwrite or not args.output.exists()
        if use_atomic_output:
            output_handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{args.output.name}.",
                suffix=".tmp",
                dir=args.output.parent,
                delete=False,
            )
            temporary_output = Path(output_handle.name)
        else:
            output_handle = args.output.open("a", encoding="utf-8", newline="\n")
        total_fetched = 0
        total_written = 0
        with output_handle:
            for question_id in dict.fromkeys(args.questions):
                print(f"Fetching question {question_id}...", file=sys.stderr)
                fetched, written = scrape_question(
                    client,
                    question_id,
                    output_handle,
                    existing_ids,
                    max_answers=args.max_answers,
                    page_size=args.page_size,
                    delay=args.delay,
                    sort_by=args.sort_by,
                )
                total_fetched += fetched
                total_written += written
                print(
                    f"Question {question_id}: fetched {fetched}, wrote {written} new answers.",
                    file=sys.stderr,
                )
        if temporary_output is not None:
            temporary_output.replace(args.output)
            temporary_output = None
        print(
            f"Done: fetched {total_fetched}, wrote {total_written} new answers to {args.output}.",
            file=sys.stderr,
        )
        return 0
    except (OSError, ScraperError) as exc:
        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
