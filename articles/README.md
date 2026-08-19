# Articles

This folder contains articles, posts, and editorial content about SOL.

## Serie in corso
- [[articles/260528_Linkedin_Presentazione/abstract|Presentazione Linkedin]]
- [[articles/260603_bizanalysis_SOL-orchestrazione/abstract|Articolo su Bizanalysis]]

## Structure

Each publication (single article or series) lives in its own subfolder named:

```
YYMMDD_Platform_Slug/
```

- `YYMMDD` — publication date (or planned date)
- `Platform` — target platform (e.g. `Linkedin`, `Medium`, `Blog`)
- `Slug` — short descriptive identifier in English or Italian, no spaces

Example: `260528_Linkedin_Presentazione/`

## Subfolder contents

| File | Purpose |
|---|---|
| `abstract.md` | Summary of the article or series: topic, target audience, goals, key messages |
| `01_title.md`, `02_title.md`, … | One file per article, numbered if part of a series |

## Author signature

Every article file must end with:

```
---
*Author: Your Name*
```

If published, add the URL:

```
---
*Author: Your Name — [Published on Platform](url)*
```

## Access

This folder is public read. Contributions via PR are welcome — no pre-registration required. See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.
