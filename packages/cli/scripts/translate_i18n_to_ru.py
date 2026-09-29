from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

DEFAULT_SOURCE = Path("packages/frontend/@n8n/i18n/src/locales/en.json")
DEFAULT_TARGET = Path("packages/frontend/@n8n/i18n/src/locales/ru.json")
DEFAULT_CACHE = Path("packages/cli/scripts/.translate-i18n-ru-cache.json")

TOKEN_PATTERNS = [
	re.compile(r"```[\s\S]*?```"),
	re.compile(r"`[^`]+`"),
	re.compile(r"<[^>]+>"),
	re.compile(r"\{\{[\s\S]*?\}\}"),
	re.compile(r"\{[a-zA-Z0-9_.-]+\}"),
	re.compile(r"%[a-zA-Z0-9_.-]+%"),
	re.compile(r"\$[a-zA-Z_][a-zA-Z0-9_.-]*"),
]


def main() -> int:
	args = parse_args()

	repo_root = Path(args.root).resolve()
	source_path = (repo_root / args.source).resolve()
	target_path = (repo_root / args.target).resolve()
	cache_path = (repo_root / args.cache).resolve()

	source = json.loads(source_path.read_text(encoding="utf-8"))
	cache = read_cache(cache_path)

	stats = {
		"translated": 0,
		"from_cache": 0,
		"unchanged": 0,
		"failed": 0,
	}

	translated = translate_value(
		source,
		cache=cache,
		path=[],
		stats=stats,
		source_lang=args.source_lang,
		target_lang=args.target_lang,
		delay_ms=args.delay_ms,
		limit=args.limit,
		force=args.force,
	)

	target_path.parent.mkdir(parents=True, exist_ok=True)
	target_path.write_text(
		json.dumps(translated, ensure_ascii=False, indent="\t") + "\n",
		encoding="utf-8",
	)

	cache_path.parent.mkdir(parents=True, exist_ok=True)
	cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")

	print(f"Wrote {target_path}")
	print(
		" ".join(
			[
				f"translated={stats['translated']}",
				f"cache={stats['from_cache']}",
				f"unchanged={stats['unchanged']}",
				f"failed={stats['failed']}",
			]
		)
	)
	return 0


def translate_value(
	value: Any,
	*,
	cache: dict[str, str],
	path: list[str],
	stats: dict[str, int],
	source_lang: str,
	target_lang: str,
	delay_ms: int,
	limit: int | None,
	force: bool,
) -> Any:
	if isinstance(value, str):
		return translate_string(
			value,
			cache=cache,
			path=path,
			stats=stats,
			source_lang=source_lang,
			target_lang=target_lang,
			delay_ms=delay_ms,
			limit=limit,
			force=force,
		)

	if isinstance(value, list):
		return [
			translate_value(
				item,
				cache=cache,
				path=[*path, str(index)],
				stats=stats,
				source_lang=source_lang,
				target_lang=target_lang,
				delay_ms=delay_ms,
				limit=limit,
				force=force,
			)
			for index, item in enumerate(value)
		]

	if isinstance(value, dict):
		result: dict[str, Any] = {}
		for key, child in value.items():
			result[key] = translate_value(
				child,
				cache=cache,
				path=[*path, key],
				stats=stats,
				source_lang=source_lang,
				target_lang=target_lang,
				delay_ms=delay_ms,
				limit=limit,
				force=force,
			)
		return result

	return value


def translate_string(
	text: str,
	*,
	cache: dict[str, str],
	path: list[str],
	stats: dict[str, int],
	source_lang: str,
	target_lang: str,
	delay_ms: int,
	limit: int | None,
	force: bool,
) -> str:
	if should_keep_unchanged(text):
		stats["unchanged"] += 1
		return text

	cache_key = f"{source_lang}:{target_lang}:{text}"
	if not force and cache_key in cache:
		stats["from_cache"] += 1
		return cache[cache_key]

	if limit is not None and stats["translated"] >= limit:
		stats["unchanged"] += 1
		return text

	protected_text, tokens = protect_tokens(text)

	try:
		translated = with_retries(
			lambda: request_translation(protected_text, source_lang=source_lang, target_lang=target_lang),
			tries=3,
			delay_ms=delay_ms,
		)
		restored = restore_tokens(translated, tokens)
		cache[cache_key] = restored
		stats["translated"] += 1
		time.sleep(delay_ms / 1000)
		return restored
	except Exception as error:
		stats["failed"] += 1
		print(f"WARN: failed to translate {'.'.join(path)}: {error}", file=sys.stderr)
		return text


def should_keep_unchanged(text: str) -> bool:
	trimmed = text.strip()
	if not trimmed:
		return True
	if re.match(r"^https?://", trimmed, flags=re.IGNORECASE):
		return True
	if re.match(r"^[\d\s.,:;+\-_/()[\]{}#@%]+$", trimmed):
		return True
	if re.match(r"^[A-Z0-9_./:-]+$", trimmed) and " " not in trimmed:
		return True
	return False


def protect_tokens(text: str) -> tuple[str, list[tuple[str, str]]]:
	tokens: list[tuple[str, str]] = []
	protected_text = text

	for pattern in TOKEN_PATTERNS:
		protected_text = pattern.sub(lambda match: replace_token(match.group(0), tokens), protected_text)

	return protected_text, tokens


def replace_token(value: str, tokens: list[tuple[str, str]]) -> str:
	token = f"__N8N_TOKEN_{len(tokens)}__"
	tokens.append((token, value))
	return token


def restore_tokens(text: str, tokens: list[tuple[str, str]]) -> str:
	restored = text
	for token, value in tokens:
		spaced_token = token.replace("_", " ")
		restored = restored.replace(token, value).replace(spaced_token, value)
	return restored


def request_translation(text: str, *, source_lang: str, target_lang: str) -> str:
	query = urllib.parse.urlencode(
		{
			"client": "gtx",
			"sl": source_lang,
			"tl": target_lang,
			"dt": "t",
			"q": text,
		}
	)
	request = urllib.request.Request(
		f"{GOOGLE_TRANSLATE_URL}?{query}",
		headers={"User-Agent": "Mozilla/5.0 n8n-i18n-local-script"},
	)

	with urllib.request.urlopen(request, timeout=30) as response:
		if response.status < 200 or response.status >= 300:
			raise RuntimeError(f"Google Translate returned {response.status}")
		payload = json.loads(response.read().decode("utf-8"))

	chunks = payload[0] if payload else None
	if not isinstance(chunks, list):
		raise RuntimeError("Unexpected Google Translate response shape")

	return "".join(str(chunk[0] or "") for chunk in chunks if isinstance(chunk, list))


def with_retries(callback, *, tries: int, delay_ms: int) -> str:
	last_error: Exception | None = None
	for attempt in range(1, tries + 1):
		try:
			return callback()
		except Exception as error:
			last_error = error
			time.sleep((delay_ms * attempt * 2) / 1000)
	assert last_error is not None
	raise last_error


def read_cache(path: Path) -> dict[str, str]:
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
		return data if isinstance(data, dict) else {}
	except FileNotFoundError:
		return {}
	except json.JSONDecodeError:
		return {}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Translate n8n frontend en.json to ru.json using the free Google Translate endpoint.",
	)
	parser.add_argument("--root", default=".", help="Repository root. Default: current directory")
	parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=f"Source locale JSON")
	parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="Target locale JSON")
	parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Translation cache JSON")
	parser.add_argument("--source-lang", default="en", help="Source language. Default: en")
	parser.add_argument("--target-lang", default="ru", help="Target language. Default: ru")
	parser.add_argument("--delay-ms", type=int, default=120, help="Delay between requests. Default: 120")
	parser.add_argument("--limit", type=int, default=None, help="Translate only N new strings")
	parser.add_argument("--force", action="store_true", help="Ignore cache and translate everything again")
	return parser.parse_args()


if __name__ == "__main__":
	raise SystemExit(main())
