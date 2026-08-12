# Primary Evidence Archive PR1

Issue: #414

This slice adds archive/retrieval metadata around the existing #144 SourceRecord authority.

## Authority boundary

- `source_id` is always an existing #144 SourceRecord identity.
- #414 does not generate a second source identity.
- filename is display/storage metadata, not identity.
- same hash across different source IDs is only a binary dedup candidate and never silently merges SourceRecords.

## Access states

- `ARCHIVED`: `archive_ref` is required and retrievable by contract.
- `URL_ONLY`: official/original URL may exist, but no archived binary is claimed.
- `UNAVAILABLE`: source is currently unavailable.
- `NEEDS_RECOVERY`: source was expected/previously available but recovery is required.

Explicit transitions preserve the previous state as a transition record. Missing external objects do not delete source history.

## Deferred to PR2

- binary storage backend selection
- Git LFS adoption
- external immutable archive selection
- bulk historical PDF ingestion
- Pages Source Library
