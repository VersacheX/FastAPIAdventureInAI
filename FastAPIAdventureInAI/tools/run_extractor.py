#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple CLI to run domain-aware extractors and print results to the terminal.

Usage:
	python run_extractor.py <url1> [<url2> ...]

If no URLs are provided the script runs two example URLs (Wikipedia and AnimeCharacters).

This script adjusts sys.path to make the package-level `services` imports work when run
from the repository root.
"""
import sys
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

# Ensure the FastAPIAdventureInAI package directory is on sys.path so "services" imports work
HERE = Path(__file__).resolve().parent
# Find the package directory by looking for a directory that contains the `services` package
# or an `__init__.py`. Prefer the current directory, then its parent, then walk up a few levels.
PKG_DIR = None
candidates = [HERE, HERE.parent, HERE.parent.parent, HERE.parent.parent.parent]
for cand in candidates:
    if (cand / "services").exists() or (cand / "__init__.py").exists():
        PKG_DIR = cand
        break

# Fallback: use HERE.parent if nothing better found
if PKG_DIR is None:
    PKG_DIR = HERE.parent

if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

# Import after ensuring the package directory is on sys.path
from services.extractor_factory import get_extractor_for_url

async def run(urls):
    for url in urls:
        print("\n" + "=" *80)
        print(f"URL: {url}")
        extractor = get_extractor_for_url(url)
        print(f"Using extractor: {extractor.__name__}")
        try:
            result = await extractor(url)
        except Exception as e:
            print(f"Extractor raised exception: {e}")
            result = None

        # Print pretty JSON (allow unicode) and write to file in C:\\temp
        try:
            json_text = json.dumps(result, indent=2, ensure_ascii=False)
            #print(json_text)
            # write to file
            try:
                out_dir = Path("C:/temp")
                out_dir.mkdir(parents=True, exist_ok=True)
                # sanitize filename using hostname and path/query
                p = urlparse(url)
                host = p.hostname or "output"
                # use path + query as part of name, replace unsafe chars
                name_raw = host + (p.path or "")
                if p.query:
                    name_raw += "_" + p.query
                name = re.sub(r'[^A-Za-z0-9._-]+', '_', name_raw)
                if len(name) >200:
                    name = name[:200]
                filepath = out_dir / (name + ".json")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(json_text)
                print(f"Wrote output to {filepath}")
            except Exception as e:
                print(f"Failed to write output file: {e}")
        except Exception:
            print(result)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = [
            #"https://leagueoflegends.fandom.com/wiki/Samira",
            #"https://wiki.leagueoflegends.com/en-us/Universe:Samira",
            #"https://www.leagueoflegends.com/en-us/champions/samira",
            #"https://finalfantasy.fandom.com/wiki/Paine",
            #"https://www.halloweencostumes.com/womens-classic-scooby-doo-daphne-costume.html",
            #"https://www.costumerealm.com/daphne-halloween-costume/",
            #"https://finalfantasy.fandom.com/wiki/Rikku",
            #"https://gamicus.fandom.com/wiki/Rikku",
            #"https://fanlore.org/wiki/Rikku",
            #"https://en.wikipedia.org/wiki/Characters_of_Final_Fantasy_X_and_X-2",
            #"https://www.animecharactersdatabase.com/characters.php?id=22961",
            #"https://en.wikipedia.org/wiki/Sakura_Haruno",
            "https://witchcraftandwitches.com/book-of-shadows/terms-book-of-shadows",
            "https://witchcraftandwitches.com/witchcraft/terms-witch-bottle",
            "http://www.schoolofburlesque.com"
        ]
        print("No URLs provided, running example URLs:\n " + "\n ".join(args))

    asyncio.run(run(args))
