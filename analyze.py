"""Compare the official Slovak name-day calendar with first names actually in use.

Inputs:
  data/*.json    open-data "residents by first name" exports of Slovak cities
  sources/official_calendarium_2025.txt
                 text of the official calendarium of the Ministry of Culture
  sources/wikipedia_meniny.wiki
                 long customary list from sk.wikipedia, used only for dates
Outputs (CSV, UTF-8 with BOM so Excel opens them correctly):
  out/name_counts.csv        every first name with its count in the sample
  out/calendar_rare.csv      official calendar names that almost nobody bears
  out/common_missing.csv     common names missing from the official calendar
  out/proposed_calendar.csv  per-day proposal: common names to add to free slots
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
OFFICIAL = os.path.join("sources", "official_calendarium_2025.txt")
WIKIPEDIA = os.path.join("sources", "wikipedia_meniny.wiki")
MAX_NAMES_PER_DAY = 4   # rule of the Calendar Commission at the Ministry of Culture
MIN_TO_PROPOSE = 50     # sample count (~400 people nationwide) below which we propose nothing


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


def parse_official(path):
    """Return {(month, day): [names in the official order]}.

    The file is `pdftotext -raw` output of the ministry's PDF. The -layout mode
    is not usable: it drops the last column of some rows onto unrelated lines.
    """
    days = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            match = re.match(r"^(\d+)\. (\d+)\.\s*(.*)$", line.strip())
            if match:
                names = [n for n in match.group(3).split() if n != "-"]
                days[(int(match.group(2)), int(match.group(1)))] = names
    if len(days) != 366:
        sys.exit("official calendarium: expected 366 days, got %d" % len(days))
    return days


def parse_wikipedia(path):
    """Return {(month, day): [names]} from the sk.wikipedia wikitext.

    Wikipedia carries the long traditional list (about 1 600 names). It is not
    official; we use it only to learn on which date an unofficial name is
    customarily celebrated, so that a proposal can name a concrete day.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    days = {}
    for month_index, month in enumerate(MONTHS, start=1):
        match = re.search(r"=== %s ===\n(.*?)(?=\n===|\n==|\Z)" % month, text, re.S)
        if not match:
            sys.exit("month section not found: " + month)
        day = 0
        for line in match.group(1).splitlines():
            if line.startswith("#"):
                day += 1
                days[(month_index, day)] = [link.split("|")[-1].strip()
                                            for link in re.findall(r"\[\[(.*?)\]\]", line)]
    return days


def parse_calendar():
    """Return {(month, day): {"main": official names, "extra": customary extras}}."""
    official = parse_official(OFFICIAL)
    wikipedia = parse_wikipedia(WIKIPEDIA)
    official_keys = {fold(n) for names in official.values() for n in names}
    calendar = {}
    for date, names in official.items():
        extra = []
        for name in wikipedia.get(date, []):
            # A name the official calendar already has on any date is not a candidate.
            if fold(name) not in official_keys and name not in extra:
                extra.append(name)
        calendar[date] = {"main": names, "extra": extra}
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
    calendar = parse_calendar()

    def display(key):
        return spellings[key].most_common(1)[0][0]

    def gender(key):
        return genders[key].most_common(1)[0][0] if genders[key] else "?"

    def tag(date):
        return "%d.%d." % (date[1], date[0])

    main_keys, extra_keys = {}, {}
    for date, names in sorted(calendar.items()):
        for n in names["main"]:
            main_keys.setdefault(fold(n), (n, date))
        for n in names["extra"]:
            extra_keys.setdefault(fold(n), (n, date))

    def status(key):
        return "official" if key in main_keys else "customary" if key in extra_keys else "none"

    ranked = counts.most_common()
    write_csv("name_counts.csv",
              ["rank", "name", "gender", "sample_count", "est_slovakia", "calendar_status", "calendar_date"],
              [[i, display(k), gender(k), c, round(c * scale), status(k),
                tag((main_keys.get(k) or extra_keys.get(k))[1]) if status(k) != "none" else ""]
               for i, (k, c) in enumerate(ranked, start=1)])

    rare = sorted(((counts.get(k, 0), n, d) for k, (n, d) in main_keys.items()),
                  key=lambda r: (r[0], r[1]))
    write_csv("calendar_rare.csv", ["name", "date", "sample_count", "est_slovakia"],
              [[n, tag(d), c, round(c * scale)] for c, n, d in rare])

    missing = [(c, k) for k, c in ranked if k not in main_keys]
    write_csv("common_missing.csv",
              ["name", "gender", "sample_count", "est_slovakia", "customary_date"],
              [[display(k), gender(k), c, round(c * scale),
                tag(extra_keys[k][1]) if k in extra_keys else ""]
               for c, k in missing if c >= 20])

    # The commission never removes Christian names and puts new names after the
    # traditional ones, so the proposal only fills free slots of a day with the
    # most used names customarily celebrated on it.
    proposal, added = [], 0
    for date, names in sorted(calendar.items()):
        free = MAX_NAMES_PER_DAY - len(names["main"])
        extras = sorted(names["extra"], key=lambda n: -counts.get(fold(n), 0))
        add = [n for n in extras if counts.get(fold(n), 0) >= MIN_TO_PROPOSE][:max(free, 0)]
        added += len(add)
        proposal.append([tag(date),
                         ", ".join("%s (%d)" % (n, counts.get(fold(n), 0)) for n in names["main"]),
                         ", ".join("%s (%d)" % (n, counts.get(fold(n), 0)) for n in add)])
    write_csv("proposed_calendar.csv",
              ["date", "official_names (sample count)", "proposed_additions (sample count)"], proposal)

    print("cities:", cities, "people:", total, "distinct names:", len(counts),
          "scale to SK: x%.2f" % scale)
    print("official names:", len(main_keys), "customary extras:", len(extra_keys),
          "proposed additions:", added)
    print("\nRAREST OFFICIAL NAMES (sample count):")
    print(", ".join("%s %d" % (n, c) for c, n, d in rare[:60]))
    print("\nofficial names with <10 bearers in sample:", sum(1 for r in rare if r[0] < 10),
          "| <50:", sum(1 for r in rare if r[0] < 50))
    print("\nTOP NAMES NOT IN THE OFFICIAL CALENDAR (* = no customary date either):")
    print(", ".join("%s %d%s" % (display(k), c, "" if k in extra_keys else "*")
                    for c, k in missing[:80]))
    covered = sum(c for k, c in counts.items() if k in main_keys)
    print("\nshare of people whose name is in the official calendar: %.1f%%" % (100 * covered / total))


if __name__ == "__main__":
    main()
