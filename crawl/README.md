# Zhihu answer exporter

This tool exports publicly accessible answers from one or more Zhihu questions to
UTF-8 JSONL. It is intended for research-note collection, not bulk mirroring.

## Usage

From either Command Prompt (CMD) or PowerShell, run this from the repository root:

```bat
python crawl\zhihu_scraper.py 529408913
```

By default, the exporter reads your browser session from `crawl/cookie.txt`,
fetches all available answers, and writes this example to
`crawl/529408913zhihu_answer.json`. The cookie file must contain one raw `Cookie`
header line. When scraping multiple questions in one command, provide `--output`
explicitly.

You can still override the defaults when needed:

```bat
python crawl\zhihu_scraper.py 529408913 --cookie-file D:\private\zhihu-cookie.txt --output crawl\data\quant_ideas.jsonl --max-answers 100
```

The default delay is two seconds between API pages. Existing JSONL output is
resumed and deduplicated by `answer_id`; use `--overwrite` only when replacement
is intentional. The default `--max-answers 0` requests all available answers.

Each record includes question and answer IDs, title, public author fields,
engagement counts, timestamps, plain text, image URLs, outgoing links, the
canonical source URL, and collection time. Treat popularity as a discovery
signal only: it is not evidence that a trading claim is true or reproducible.

Respect Zhihu's current terms, robots policy, copyright, and rate limits. Do not
use this tool to bypass login, CAPTCHA, paid content, deleted content, or other
access controls. Cookies are credentials: keep them local, rotate exposed ones,
and never commit them.
