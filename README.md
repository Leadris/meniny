# Meniny (meniny.cukivan.me)

A citizen proposal to bring the Slovak name-day calendar in line with the names people
actually bear. The calendar still headlines names almost nobody has (Pankrác, Servác,
Svätopluk) while common ones (Sofia, Nela, Tobias) have no headline slot. The site shows
the numbers and lets visitors vote which name should headline each day.

## Data

- `data/*.json`: "residents by first name" open data of 18 Slovak cities (POMOSAM
  portals, `https://egov.<city>.sk/Default.aspx?NavigationState=925:0::plac2171:_144151_5_8`),
  downloaded 2026-11-12. 660 299 people, about 12 % of Slovakia. Poprad publishes the
  dataset too but its export returned an HTML page.
- `calendar.wiki`: wikitext of sk.wikipedia "Meniny na Slovensku". Bold names are the
  headline names printed in calendars, the rest is the extended list. Wikipedia itself
  notes it is not fully aligned with the official calendar of the Ministry of Culture.

Known bias: cities only, and Komárno and Dunajská Streda over-represent Hungarian names.
National figures are the sample count scaled by population, so treat them as estimates.

## Scripts

    python analyze.py      # CSV reports into out/ and a summary on stdout
    python build_site.py   # site/data/names.json, the only data file the site reads

Names are matched ignoring case and diacritics, and only the first given name counts.

## Site

`site/` is plain HTML, CSS and JS with no build step. `site/api/vote.php` stores votes
in `site/api/store/votes.json` (one vote per calendar day per visitor, identified by a
salted hash of the IP address; the salt is generated on the server). Only names the
calendar already lists for a day can be voted for.

Run locally (PHP 8.1+):

    php -S localhost:8765 -t site

The page carries `noindex` until the owner decides to make it public.

## Deploy

    pwsh -NoProfile -File scripts\deploy.ps1 -Server <host> -User <user> -Go

Without `-Go` it only lists what would be uploaded. Nothing on the server is deleted, so
votes survive deploys. The subdomain and its HTTPS certificate are created in the WebHouse
panel by the owner.
