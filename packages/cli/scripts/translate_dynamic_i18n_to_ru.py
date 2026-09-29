from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent

DEFAULT_SKELETON = SCRIPT_DIR / ".dynamic-i18n-skeleton.json"
DEFAULT_CACHE = SCRIPT_DIR / ".translate-i18n-ru-cache.json"
DEFAULT_NODES_BASE = SCRIPT_DIR.parent.parent / "nodes-base"


def load_base_translator():
	spec = importlib.util.spec_from_file_location(
		"translate_i18n_to_ru", SCRIPT_DIR / "translate_i18n_to_ru.py"
	)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def main() -> int:
	args = parse_args()
	base = load_base_translator()

	skeleton_path = Path(args.skeleton).resolve()
	cache_path = Path(args.cache).resolve()
	nodes_base_dir = Path(args.nodes_base).resolve()

	aggregate: dict[str, Any] = json.loads(skeleton_path.read_text(encoding="utf-8"))
	cache = base.read_cache(cache_path)

	stats = {"translated": 0, "from_cache": 0, "unchanged": 0, "failed": 0}

	written = 0
	for rel_path, skeleton in aggregate.items():
		translated = base.translate_value(
			skeleton,
			cache=cache,
			path=[rel_path],
			stats=stats,
			source_lang=args.source_lang,
			target_lang=args.target_lang,
			delay_ms=args.delay_ms,
			limit=args.limit,
			force=args.force,
		)

		out_path = (nodes_base_dir / rel_path).resolve()
		out_path.parent.mkdir(parents=True, exist_ok=True)
		out_path.write_text(
			json.dumps(translated, ensure_ascii=False, indent="\t") + "\n",
			encoding="utf-8",
		)
		written += 1

	cache_path.parent.mkdir(parents=True, exist_ok=True)
	cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")

	print(f"Wrote {written} translation files under {nodes_base_dir}")
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


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Translate the node/credential dynamic-text skeleton "
			"(from extract-dynamic-i18n-skeleton.js) to ru and write "
			"packages/nodes-base/**/translations/ru/*.json files."
		),
	)
	parser.add_argument("--skeleton", default=str(DEFAULT_SKELETON), help="Skeleton aggregate JSON")
	parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="Translation cache JSON (shared with the base-text script)")
	parser.add_argument("--nodes-base", default=str(DEFAULT_NODES_BASE), help="packages/nodes-base directory")
	parser.add_argument("--source-lang", default="en", help="Source language. Default: en")
	parser.add_argument("--target-lang", default="ru", help="Target language. Default: ru")
	parser.add_argument("--delay-ms", type=int, default=120, help="Delay between requests. Default: 120")
	parser.add_argument("--limit", type=int, default=None, help="Translate only N new strings")
	parser.add_argument("--force", action="store_true", help="Ignore cache and translate everything again")
	return parser.parse_args()


if __name__ == "__main__":
	raise SystemExit(main())
