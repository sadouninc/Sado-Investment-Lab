# Primary Evidence Archive PR4 — Coverage Audit

Issue: #414

This slice makes Evidence coverage gaps explicit before historical recovery starts.

## Initial audit targets

- 3110 日東紡
- 6622 ダイヘン
- 6504 富士電機
- 5805 SWCC
- 6758 ソニーグループ
- 6376 日機装

## Observed canonical Research baseline

At implementation time, `data/research/company/` contains canonical Company Research for 6622 and 7974. Among the six #414 initial audit targets, only 6622 currently has canonical Company Research in that SSoT.

PR4 does not invent missing Research or source identities. It reports explicit states:

- `RESEARCH_MISSING`
- `SOURCE_ID_MISSING`
- `URL_ONLY`
- `ARCHIVED`
- `NEEDS_RECOVERY`
- `UNAVAILABLE`
- `PARTIAL`

A missing archive record for a known #144 source is `URL_ONLY`; it is not silently treated as archived. Missing canonical Research is not converted into an inferred Recovery item.

## Next recovery action

After this audit lands, recovery should proceed from known Primary sources first. Daihen is the first deterministic candidate because its CURRENT Research already declares the FY2027-Q1 official IR source. Other target companies should enter recovery only after their canonical Research/source catalog is established, or after a concrete Primary document is received and registered through #144/#414.
