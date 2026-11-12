"""Compare the Slovak name-day calendar with first names actually in use.

Inputs:
  data/*.json          open-data "residents by first name" exports of Slovak cities
  calendar.wiki  wikitext of sk.wikipedia "Meniny na Slovensku"
                       (bold names = printed in calendars, the rest = extended list)
Outputs (CSV, UTF-8 with BOM so Excel opens them correctly):
  out/name_counts.csv        every first name with its count in the sample
  out/calendar_rare.csv      headline calendar names that almost nobody bears
  out/common_missing.csv     common names with no headline slot in the calendar
  out/proposed_calendar.csv  per-day proposal: headline = most used names of that day
"""
import csv
import glob
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

SK_POPULATION = 5_420_000  # used only to scale the sample to a rough national estimate
MONTHS = ["Január", "Február", "Marec", "Apríl", "Máj", "Jún", "Júl",
          "August", "September", "Október", "November", "December"]


def fold(name):
    """Key that ignores case and diacritics.

    City registries are inconsistent (Natália/Natalia, Sofia/Sofía), so exact
    matching would undercount names and report false "missing from calendar".
    """
    decomposed = unicodedata.normalize("NFD", name.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def load_counts():
    counts = Counter()                      # fold key -> people
    spellings = defaultdict(Counter)        # fold key -> spelling -> people
    genders = defaultdict(Counter)          # fold key -> gender -> people
    cities = 0
    for path in sorted(glob.glob(os.path.join("data", "*.json"))):
        with open(path, encoding="utf-8-sig") as fh:
            rows = json.load(fh)
        cities += 1
        for row in rows:
            raw = (row.get("Krstné_meno") or row.get("Meno") or "").strip()
            n = int(str(row.get("Počet", "0")).strip() or 0)
            # Only the first given name decides whose name day a person celebrates.
            tokens = re.split(r"[\s,\-]+", raw)
            if not tokens or not tokens[0] or n <= 0:
                continue
            name = tokens[0].capitalize()
            if not name.isalpha():
                continue
            key = fold(name)
            counts[key] += n
            spellings[key][name] += n
            gender = (row.get("Pohlavie") or "").strip().lower()
            if gender:  # Trnava publishes no gender; other cities fill it in
                genders[key]["M" if gender.startswith("m") else "F"] += n
    return counts, spellings, genders, cities


def parse_calendar(path):
    """Return {(month, day): {"main": [...], "extra": [...]}} from the wikitext."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    calendar = {}
    for month_index, month in enumerate(MONTHS, start=1):
        match = re.search(r"=== %s ===\n(.*?)(?=\n===|\n==|\Z)" % month, text, re.S)
        if not match:
            sys.exit("month section not found: " + month)
        day = 0
        for line in match.group(1).splitlines():
            if not line.startswith("#"):
                continue
            day += 1
            main, extra = [], []
            # Bold segments first, then whatever links remain are the extended list.
            bold_parts = re.findall(r"'''(.*?)'''", line)
            rest = re.sub(r"'''.*?'''", "", line)
            for target, part in ((main, " ".join(bold_parts)), (extra, rest)):
                for link in re.findall(r"\[\[(.*?)\]\]", part):
                    target.append(link.split("|")[-1].strip())
            calendar[(month_index, day)] = {"main": main, "extra": extra}
    return calendar


def write_csv(name, header, rows):
    os.makedirs("out", exist_ok=True)
    with open(os.path.join("out", name), "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    counts, spellings, genders, cities = load_counts()
    total = sum(counts.values())
    scale = SK_POPULATION / total
    calendar = parse_calendar("calendar.wiki")

    def display(key):
        return spellings[key].most_common(1)[0][0]

    def gender(key):
        return genders[key].most_common(1)[0][0] if genders[key] else "?"

    main_keys, extra_keys = {}, {}
    for date, names in sorted(calendar.items()):
        for n in names["main"]:
            main_keys.setdefault(fold(n), (n, date))
        for n in names["extra"]:
            extra_keys.setdefault(fold(n), (n, date))

    ranked = counts.most_common()
    write_csv("name_counts.csv",
              ["rank", "name", "gender", "sample_count", "est_slovakia", "calendar_status", "calendar_date"],
              [[i, display(k), gender(k), c, round(c * scale),
                "headline" if k in main_keys else "extended" if k in extra_keys else "none",
                "%d.%d." % (main_keys.get(k) or extra_keys.get(k) or ("", (0, 0)))[1][::-1]
                if (k in main_keys or k in extra_keys) else ""]
               for i, (k, c) in enumerate(ranked, start=1)])

    rare = sorted(((counts.get(k, 0), n, d) for k, (n, d) in main_keys.items()),
                  key=lambda r: (r[0], r[1]))
    write_csv("calendar_rare.csv", ["name", "date", "sample_count", "est_slovakia"],
              [[n, "%d.%d." % (d[1], d[0]), c, round(c * scale)] for c, n, d in rare])

    missing = [(c, k) for k, c in ranked if k not in main_keys]
    write_csv("common_missing.csv",
              ["name", "gender", "sample_count", "est_slovakia", "calendar_status", "extended_date"],
              [[display(k), gender(k), c, round(c * scale),
                "extended" if k in extra_keys else "none",
                "%d.%d." % extra_keys[k][1][::-1] if k in extra_keys else ""]
               for c, k in missing if c >= 20])

    # Proposal keeps every name on its traditional date and only changes which
    # names are printed: the two most used names of the day become the headline.
    proposal, changed = [], 0
    for date, names in sorted(calendar.items()):
        pool = {}
        for n in names["main"] + names["extra"]:
            pool.setdefault(fold(n), n)
        by_use = sorted(pool.items(), key=lambda kv: -counts.get(kv[0], 0))
        new_main = [n for k, n in by_use[:2] if counts.get(k, 0) > 0] or names["main"]
        if [fold(n) for n in new_main[:1]] != [fold(n) for n in names["main"][:1]]:
            changed += 1
        proposal.append(["%d.%d." % (date[1], date[0]),
                         ", ".join("%s (%d)" % (n, counts.get(fold(n), 0)) for n in names["main"]),
                         ", ".join("%s (%d)" % (n, counts.get(fold(n), 0)) for n in new_main)])
    write_csv("proposed_calendar.csv", ["date", "current_headline (sample count)", "proposed_headline (sample count)"], proposal)

    print("cities:", cities, "people:", total, "distinct names:", len(counts),
          "scale to SK: x%.2f" % scale)
    print("calendar days:", len(calendar), "headline names:", len(main_keys),
          "extended names:", len(extra_keys))
    print("days where top headline name changes:", changed)
    print("\nRAREST HEADLINE NAMES (sample count):")
    print(", ".join("%s %d" % (n, c) for c, n, d in rare[:70]))
    print("\nheadline names with <10 bearers in sample:", sum(1 for r in rare if r[0] < 10),
          "| <50:", sum(1 for r in rare if r[0] < 50))
    print("\nTOP NAMES WITHOUT HEADLINE SLOT:")
    print(", ".join("%s %d%s" % (display(k), c, "" if k in extra_keys else "*")
                    for c, k in missing[:90]))
    covered = sum(c for k, c in counts.items() if k in main_keys)
    print("\nshare of people whose name is a headline name: %.1f%%" % (100 * covered / total))
    print("share with any calendar entry: %.1f%%" % (
        100 * sum(c for k, c in counts.items() if k in main_keys or k in extra_keys) / total))
    for probe in ("Svätopluk", "Winnetou"):
        print(probe, counts.get(fold(probe), 0))


if __name__ == "__main__":
    main()
