# Meniny (cukivan.me/meniny)

Public numbers for the Slovak name-day calendar: how many people actually bear each
name, which official calendar names almost nobody has (Pankrác, Servác, Prokop) and which
names in use are missing. The official calendar is kept by the Calendar Commission at the
Ministry of Culture, which adds names on citizens' requests; this site is meant as input
for it, not a rival calendar. Visitors can look up their name, play a guessing game and
vote which name a day deserves most.

## Data

- `data/*.json`: "residents by first name" open data of 18 Slovak cities (POMOSAM
  portals, `https://egov.<city>.sk/Default.aspx?NavigationState=925:0::plac2171:_144151_5_8`),
  downloaded 2026-11-12. 660 299 people, about 12 % of Slovakia. Poprad publishes the
  dataset too but its export returned an HTML page.
- `sources/official_calendarium_2025.txt`: `pdftotext -raw` text of the official
  calendarium published by the Ministry of Culture
  (https://www.culture.gov.sk/sk/oficialne-kalendarium). Up to four names per day in a
  set order; this is what "official" means everywhere in the code.
- `sources/wikipedia_meniny.wiki`: wikitext of sk.wikipedia "Meniny na Slovensku", the
  long customary list. Used only to know on which day an unofficial name is usually
  celebrated, so a proposal can name a concrete date.

- `sources/name_origins.json`: intro of each official name's article on sk.wikipedia
  (CC BY-SA 4.0). The site quotes only the sentences about origin or meaning and links
  the article.

The commission's rules shape the proposal: Christian names are never removed, new names
follow the traditional ones, and a day holds at most four names. So `analyze.py` only
proposes additions to free slots, never replacements.

Known bias: cities only, and Komárno and Dunajská Streda over-represent Hungarian names.
National figures are the sample count scaled by population, so treat them as estimates.

## Scripts

    python analyze.py      # CSV reports into out/ and a summary on stdout
    python build_site.py   # site/data/names.json, the only data file the site reads
    python fetch_origins.py  # refresh sources/name_origins.json from sk.wikipedia (rarely)

Names are matched ignoring case and diacritics, and only the first given name counts.
For a name missing from the official calendar the site shows the closest official name
(Miriam -> Miriama); that match is automatic and only a hint.

## Site

`site/` is plain HTML, CSS and JS with no build step. `site/api/vote.php` stores votes
in `site/api/store/votes.json` (one vote per calendar day per visitor, identified by a
salted hash of the IP address; the salt is generated on the server). Votable are the
official names of a day and the customary names proposed for it.

Run locally (PHP 8.1+):

    php -S localhost:8765 -t site

## Deploy

    pwsh -NoProfile -File scripts\deploy.ps1 -Server <host> -User <user> -Go

Without `-Go` it only lists what would be uploaded. Nothing on the server is deleted, so
votes survive deploys. The site is a subpage of cukivan.me, so it shares its certificate.
