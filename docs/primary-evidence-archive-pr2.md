# Primary Evidence Archive PR2 — GitHub Immutable Release Assets

Issue: #414

PR1 established archive metadata around the existing #144 SourceRecord authority. PR2 selects and constrains the binary archive backend.

## Decision

Primary evidence binaries are stored as GitHub Release assets. The normal Git history stores only provenance/registry metadata.

Git LFS is not selected because GitHub Pages does not support Git LFS files. Direct Git storage is not selected because recurring decision/IR PDFs would permanently grow repository history and clone/CI cost.

## Immutability gate

An uploaded asset MUST NOT be promoted to `ARCHIVED` unless the release is confirmed immutable.

When immutable status cannot be confirmed, or the asset cannot be retrieved or verified, keep/downgrade the registry state to `URL_ONLY`, `NEEDS_RECOVERY`, or `UNAVAILABLE` as appropriate. Never infer a successful archive from an upload attempt alone.

Repository-level immutable releases must be enabled before production ingestion begins.

## Source and binary identity

- #144 `source_id` remains the only canonical Source identity.
- A release tag is derived from `source_id` only to create a deterministic archive location; it is not a new Source identity.
- Asset names are namespaced by `source_id` to avoid filename collisions.
- SHA-256 identifies binary equality candidates, not Source equality.
- If another SourceRecord has the same SHA-256, it may reuse the already archived immutable binary `archive_ref`; the SourceRecords remain distinct.
- The same SHA-256 pointing at more than one archived binary fails closed for audit rather than choosing silently.

## Canonical layout

For `source:0123456789abcdef01234567` and `results.pdf`:

```text
release tag: evidence-source-0123456789abcdef01234567
asset name:  source-0123456789abcdef01234567__results.pdf
archive_ref: https://github.com/sadouninc/Sado-Investment-Lab/releases/download/<tag>/<asset>
```

## Ingest contract

A release-capable caller creates a draft release, attaches the binary, publishes it under repository immutable-release protection, then passes the GitHub release-asset response to `validate_uploaded_asset()`.

Promotion to `ARCHIVED` requires all of:

1. release is confirmed immutable
2. GitHub asset state is `uploaded`
3. asset size is below GitHub's 2 GiB per-asset limit
4. asset name and browser download URL match the deterministic contract
5. GitHub's `sha256:` digest matches the locally calculated SHA-256

Only after those checks should the PR1 archive record be transitioned to `ARCHIVED` with the returned `archive_ref` and SHA-256.

## Retrieve contract

`GitHubReleaseArchiveAdapter.retrieve()` accepts only Release download URLs for this repository. Every retrieved payload is re-hashed and compared with the registry SHA-256 before it is returned to consumers.

A mismatch is evidence corruption/tampering and fails closed.

## Agent / Pages accessibility

The repository is public, so immutable Release assets are directly retrievable by browser, Pages links, and agents that can perform normal HTTP/GitHub reads. Pages therefore links to `archive_ref`; it does not need to contain or build the PDF itself.

## Operational boundary

PR2 defines and validates the archive adapter. It does not bulk-import historical PDFs and does not yet change Company Research or Pages UI. Those remain PR3–PR5 work under #414.

The connector used during implementation cannot read the repository immutable-release setting (403), so production ingestion remains fail-closed until that setting is independently confirmed enabled.
