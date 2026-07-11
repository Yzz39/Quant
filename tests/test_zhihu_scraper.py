import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawl"))

from zhihu_scraper import (  # noqa: E402
    ScraperError,
    build_parser,
    html_to_text_and_assets,
    load_existing_answer_ids,
    normalize_answer,
    parse_question_id,
    resolve_output_path,
)


def test_command_defaults_fetch_all_and_use_local_cookie() -> None:
    args = build_parser().parse_args(["529408913"])

    assert args.questions == ["529408913"]
    assert args.max_answers == 0
    assert args.cookie_file == Path("crawl/cookie.txt")
    assert args.output is None
    assert (
        resolve_output_path(args.output, args.questions)
        == Path("crawl/529408913zhihu_answer.json")
    )


def test_multiple_questions_require_an_explicit_output() -> None:
    with pytest.raises(ValueError, match="--output is required"):
        resolve_output_path(None, ["1", "2"])

    assert resolve_output_path(Path("answers.json"), ["1", "2"]) == Path(
        "answers.json"
    )


def test_parse_question_id_accepts_id_and_url() -> None:
    assert parse_question_id("529408913") == "529408913"
    assert (
        parse_question_id("https://www.zhihu.com/question/529408913/answer/123")
        == "529408913"
    )


def test_html_to_text_and_assets_preserves_structure() -> None:
    text, images, links = html_to_text_and_assets(
        '<p>First <b>idea</b></p><ul><li>Risk</li></ul>'
        '<img data-original="//pic.example/chart.png" alt="chart">'
        '<a href="/question/1">source</a><script>ignore me</script>'
    )

    assert "First idea" in text
    assert "- Risk" in text
    assert "ignore me" not in text
    assert images == ["https://pic.example/chart.png"]
    assert links == ["https://www.zhihu.com/question/1"]


def test_normalize_answer_produces_research_record() -> None:
    item = normalize_answer(
        {
            "id": 456,
            "question": {"id": 123, "title": "A question"},
            "author": {"id": "author-id", "name": "Alice"},
            "content": "<p>Trend following</p>",
            "excerpt": "Trend",
            "voteup_count": 12,
            "comment_count": 3,
            "created_time": 0,
            "updated_time": 1,
        },
        "999",
    )

    assert item["answer_id"] == "456"
    assert item["question_id"] == "123"
    assert item["content_text"] == "Trend following"
    assert item["url"] == "https://www.zhihu.com/question/123/answer/456"
    assert item["created_at"] == "1970-01-01T00:00:00Z"


def test_resume_ids_and_invalid_jsonl(tmp_path: Path) -> None:
    output = tmp_path / "answers.jsonl"
    output.write_text(
        json.dumps({"answer_id": "1"}) + "\n" + json.dumps({"answer_id": "2"}),
        encoding="utf-8",
    )
    assert load_existing_answer_ids(output) == {"1", "2"}

    output.write_text('{"answer_id": "1"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(ScraperError, match="not valid JSONL"):
        load_existing_answer_ids(output)
