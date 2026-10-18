# 4. Market data stays local, and proprietary fund data is not imitated

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The data private markets research uses - fund-level cash flows from Burgiss, Preqin or
Cambridge Associates - is licensed and not public. Public index histories are freely
downloadable from Yahoo Finance, but the quotes are Yahoo's to license, not a public
repository's to republish.

## Decision

- **Index histories are fetched by `pmlab market fetch` into the git-ignored
  `data/market`.** Charts that need them are skipped where they are absent, in CI among
  other places.
- **No dataset is presented as real fund data.** Fund cash flows in this lab come from
  two sources:
  - the stylised and (from Day 3) calibrated models, labelled as such;
  - published academic figures, which are cited as references or calibration targets,
    never redistributed as data.
- **Public-domain series (FRED, FHFA) are used where they fit.** Any other public
  source - for instance a pension fund's published fund-level returns - is used only
  after its terms are checked, and the check is recorded.

## Consequences

- **Anyone can rerun every chart** after `pmlab market fetch`. The offline charts and the
  whole validation suite need nothing at all.
- **Findings about real-world private equity performance are stated as findings about
  methods**, shown on real index paths, unless a public data source supports more.
