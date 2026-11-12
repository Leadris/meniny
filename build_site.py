"""Build site/data/names.json, the single data file the static site reads.

The site has no build step and no database for content: everything it shows about
names comes from this file, so the numbers on the page always match analyze.py.
The same file is read by site/api/vote.php to decide which votes are valid.
"""
import difflib
import json
import os

from analyze import SK_POPULATION, fold, load_counts, parse_calendar

MAX_CANDIDATES = 8   # more options than this do not fit one phone screen
MIN_SEARCHABLE = 3   # names borne by 1-2 people could point at an individual
SIMILARITY = 0.75    # low enough for Emma -> Ema, high enough to skip unrelated names


def main():
    counts, spellings, genders, cities = load_counts()
    total = sum(counts.values())
    calendar = parse_calendar()

    # An official entry wins over a customary one when a name appears on two dates.
    status, date_of, label = {}, {}, {}
    for kind, tag in (("main", "official"), ("extra", "customary")):
        for date, names in sorted(calendar.items()):
            for name in names[kind]:
                key = fold(name)
                if key not in status:
                    status[key], date_of[key], label[key] = tag, "%02d-%02d" % date, name

    def display(key):
        # Registries mix Slovak and foreign spellings (Svätopluk/Svatopluk);
        # for calendar names the calendar spelling is the one people look up.
        return label.get(key) or spellings[key].most_common(1)[0][0]

    official_keys = [k for k, s in status.items() if s == "official"]

    def gender(key):
        # Names absent from the sample have no recorded gender; in Slovak a final
        # "a" is a reliable enough sign of a female name for this comparison.
        if genders[key]:
            return genders[key].most_common(1)[0][0]
        return "F" if key.endswith("a") else "M"

    def nearest(key):
        # Many "missing" names are only another form of an official one
        # (Miriam/Miriama, Ingrid/Ingrida). Showing the closest official name tells
        # the bearer when they most likely celebrate and keeps the gap honest.
        # Same first letter and same gender weed out look-alikes that are different
        # names (Emily/Emil, Marie/Mário, Amélia/Melisa).
        for other in difflib.get_close_matches(key, official_keys, n=5, cutoff=SIMILARITY):
            if other[0] == key[0] and gender(other) == gender(key):
                return [label[other], date_of[other]]
        return None

    days = {}
    for date, names in sorted(calendar.items()):
        official = [fold(n) for n in names["main"]]
        pool = {fold(n): n for n in names["extra"]}
        extras = sorted((k for k in pool if counts.get(k, 0) > 0),
                        key=lambda k: (-counts[k], pool[k]))
        # Official names always stay votable, even with zero bearers, so people
        # can stand up for tradition as well as ask for an addition.
        room = max(MAX_CANDIDATES - len(official), 0)
        days["%02d-%02d" % date] = {
            "current": names["main"],
            "candidates": [[n, counts.get(fold(n), 0), 1] for n in names["main"]]
                          + [[pool[k], counts[k], 0] for k in extras[:room]],
        }

    names = []
    for key, count in counts.most_common():
        if count < MIN_SEARCHABLE:
            break
        entry = [display(key), count, status.get(key, "none"), date_of.get(key, "")]
        if status.get(key) != "official":
            close = nearest(key)
            if close:
                entry.append(close)
        names.append(entry)
    # Official names nobody in the sample bears still belong in the list.
    for key in official_keys:
        if counts.get(key, 0) < MIN_SEARCHABLE:
            names.append([label[key], counts.get(key, 0), "official", date_of[key]])

    covered = sum(c for k, c in counts.items() if status.get(k) == "official")
    payload = {
        "meta": {"cities": cities, "people": total,
                 "scale": round(SK_POPULATION / total, 2),
                 "covered": round(100 * covered / total, 1),
                 "official_names": len(official_keys)},
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
