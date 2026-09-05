# Contributing to SOL

## The spec is the source of truth

The spec file (`spec/sol-X.Y.Z.md`) is the authoritative definition of SOL. Every other artifact — JSON schema, README, DESIGN.md, examples — derives from it.

When making changes:

1. **Change the spec first.** If it is not in the spec, it is not SOL.
2. **Update derived artifacts to match:** schema, README, DESIGN.md, examples.
3. **Never update documentation or schema to reflect behavior not yet in the spec.** Documentation describes the spec; it does not define it.

---

SOL is a spec project. Contributions can be:

- **Issues** — questions, edge cases, ambiguities in the spec
- **Proposals** — new instructions or changes to existing semantics
- **Examples** — real-world SOL processes
- **Corrections** — errors in the spec or design rationale

## Before opening a PR

1. Open an issue first for anything that changes the spec.
2. Read [`doc/DESIGN.md`](doc/DESIGN.md) — many "why not X" questions are answered there.
3. Proposals for new instructions should include: motivation, example, and edge case analysis.

## Versioning

SOL follows semantic versioning:

| Change | Version bump |
|---|---|
| Clarifications, examples, no behavior change | Patch (0.2.x) |
| New instructions or optional fields, backwards compatible | Minor (0.x.0) |
| Breaking changes to existing instruction semantics | Major (x.0.0) |

## Style

- Spec language: English
- Keep it minimal — SOL's value is partly in what it leaves out

---

## Contributing articles

The `articles/` folder is open to editorial contributions: articles, posts, case studies, translations.

No issue required — open a PR directly.

### Folder structure

Each publication lives in a subfolder named `YYMMDD_Platform_Slug/`:

- `YYMMDD` — publication date or planned date
- `Platform` — target platform (e.g. `Linkedin`, `Medium`, `Blog`)
- `Slug` — short identifier, no spaces

### File format

Each subfolder must contain:

- `abstract.md` — topic, target audience, key messages
- One `.md` file per article, numbered if part of a series: `01_title.md`, `02_title.md`, …

### Author signature

Every article file must end with an author line:

```
---
*Author: Your Name*
```

If the article has been published, add the URL:

```
---
*Author: Your Name — [Published on Platform](url)*
```
