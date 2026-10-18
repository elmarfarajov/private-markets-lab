# 3. Measures are tested against published values, independent methods, and funds whose truth is known

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

A performance measure cannot be checked against real fund data alone, because the true
skill of a real fund is unknown. Published worked examples cover the IRR and MIRR, but not
the PME family.

## Decision

Every measure is held to at least one reference that shares no code with it:

- **Published values:**
  - Microsoft's XIRR and MIRR documentation examples;
  - Lorie and Savage's (1955) two-root pump problem.
- **Independent methods:**
  - numpy-financial's IRR and MIRR;
  - polynomial roots in `1/(1 + r)`;
  - mpmath at 50 digits.
- **Identities that must hold:**
  - a fund that *is* the index scores a PME of one, an alpha of zero, and an index IRR
    equal to its own under all five methods;
  - TVPI = DPI + RVPI;
  - the PME+ account ends at the NAV;
  - the Kaplan-Schoar PME exceeds one exactly when Direct Alpha is positive.
- **Closed forms:** a single deal growing at `r` against an index growing at `g`.
- **Funds whose truth is known:** a stylised fund built deal by deal with a chosen alpha,
  beta and own risk. Direct Alpha must return the alpha of a noise-free beta-one fund
  exactly.

## Consequences

- **The published examples reproduce, with one stated limit.** XIRR matches Excel's
  printed value to 1.5e-9, the limit of Excel's own 1e-8 tolerance. MIRR matches to the
  printed digit, and the pump problem's roots to 9e-16.
- **Every identity holds to 1e-15,** mid-life with a NAV and at the end.
- **The stylised fund carries the known biases on purpose.** A PME's beta bias, for
  example, is measured rather than described.
