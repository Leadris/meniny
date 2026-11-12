"""Build site/data/names.json, the single data file the static site reads.

The site has no build step and no database for content: everything it shows about
names comes from this file, so the numbers on the page always match analyze.py.
The same file is read by site/api/vote.php to decide which votes are valid.
"""
import json
import os

from analyze import SK_POPULATION, fold, load_counts, parse_calendar

MAX_CANDIDATES = 8   # more options than this do not fit one phone screen
MIN_SEARCHABLE = 3   # names borne by 1-2 people could point at an individual


def main():
    counts, spellings, genders, cities = load_counts()
    total = sum(counts.values())
    calendar = parse_calendar("calendar.wiki")

    # A headline entry wins over an extended one when a name appears on two dates.
    status, date_of, label = {}, {}, {}
    for kind in ("main", "extra"):
        for date, names in sorted(calendar.items()):
            for name in names[kind]:
                key = fold(name)
                if key not in status:
                    status[key], date_of[key], label[key] = kind, "%02d-%02d" % date, name

    def display(key):
        # Registries mix Slovak and foreign spellings (Svätopluk/Svatopluk);
        # for calendar names the calendar spelling is the one people look up.
        return label.get(key) or spellings[key].most_common(1)[0][0]

    days = {}
    for date, names in sorted(calendar.items()):
        pool = {}
        for name in names["main"] + names["extra"]:
            pool.setdefault(fold(name), name)
        ranked = sorted(pool.items(), key=lambda kv: (-counts.get(kv[0], 0), kv[1]))
        current = [fold(n) for n in names["main"]]
        # Current headline names always stay votable, even with zero bearers,
        # so people can defend tradition as well as replace it.
        keep = [k for k, _ in ranked if counts.get(k, 0) > 0][:MAX_CANDIDATES]
        keep += [k for k in current if k not in keep]
        days["%02d-%02d" % date] = {
            "current": names["main"],
            "candidates": [[pool[k], counts.get(k, 0)] for k in keep],
        }

    names = []
    for key, count in counts.most_common():
        if count < MIN_SEARCHABLE:
            break
        names.append([display(key), count, status.get(key, "none"), date_of.get(key, "")])
    # Calendar headline names nobody in the sample bears still belong in the list.
    for key, kind in status.items():
        if kind == "main" and counts.get(key, 0) < MIN_SEARCHABLE:
            names.append([label[key], counts.get(key, 0), "main", date_of[key]])

    payload = {
        "meta": {"cities": cities, "people": total,
                 "scale": round(SK_POPULATION / total, 2), "source_date": "2026-11-12"},
        "days": days,
        "names": names,
    }
    os.makedirs(os.path.join("site", "data"), exist_ok=True)
    path = os.path.join("site", "data", "names.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print("wrote", path, os.path.getsize(path), "bytes;", len(days), "days,", len(names), "names")


if __name__ == "__main__":
    main()
