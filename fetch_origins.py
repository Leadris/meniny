"""Fetch the intro of each official name's article on sk.wikipedia.

Writes sources/name_origins.json: {name: {"text": intro, "title": article title}}.
The article title comes from the links in sources/wikipedia_meniny.wiki where
possible, because many names share a title with something else and live under
"Name (prvé meno)". Run rarely: the result is committed so the site build does
not depend on the network.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from analyze import OFFICIAL, WIKIPEDIA, fold, parse_official

API = "https://sk.wikipedia.org/w/api.php"
BATCH = 20  # the extracts API returns at most 20 intros per request


def linked_titles():
    titles = {}
    with open(WIKIPEDIA, encoding="utf-8") as fh:
        for target in re.findall(r"\[\[(.*?)\]\]", fh.read()):
            title, _, shown = target.partition("|")
            titles.setdefault(fold((shown or title).strip()), title.strip())
    return titles


def fetch(titles):
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "extracts", "exintro": 1,
        "explaintext": 1, "redirects": 1, "exlimit": BATCH, "titles": "|".join(titles)})
    request = urllib.request.Request(API + "?" + query, headers={"User-Agent": "name-day-research/1.0"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)["query"]
            break
        except urllib.error.HTTPError as error:
            # Wikipedia throttles anonymous bursts with 429; wait as told and retry.
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(int(error.headers.get("Retry-After") or 0) or 10 * (attempt + 1))
    moved = {r["from"]: r["to"] for r in data.get("redirects", []) + data.get("normalized", [])}
    pages = {p["title"]: p.get("extract", "") for p in data["pages"].values()}
    return {t: (moved.get(t, t), pages.get(moved.get(t, t), "")) for t in titles}


def main():
    known = linked_titles()
    names = [n for day in parse_official(OFFICIAL).values() for n in day]
    wanted = {n: known.get(fold(n), n) for n in dict.fromkeys(names)}
    result = {}
    titles = sorted(set(wanted.values()))
    for start in range(0, len(titles), BATCH):
        got = fetch(titles[start:start + BATCH])
        for name, title in wanted.items():
            if title in got and got[title][1].strip():
                result[name] = {"title": got[title][0], "text": got[title][1].strip()}
        time.sleep(2)  # be polite to the API
    with open("sources/name_origins.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("names:", len(wanted), "with article text:", len(result))


if __name__ == "__main__":
    main()
