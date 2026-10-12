# Change log

Changes affecting partners or operations are recorded here, with evidence and follow-up linked separately.

## Unreleased — pipeline recovery, 2026-10-12

- Pin the complete runtime/test dependency set, including the working Narwhals version; pin CI actions and the container base.
- Validate refreshes in a separate directory. Failed collection, analysis, or validation returns a failing exit code and preserves the previous data. CI tests both snapshots before publishing one data commit.
- Retain removed ISINs and their metadata as inactive; include new listings without trades explicitly. Current views use active listings; historical views and exports retain history. Unobserved listings are unassessed.
- Normalize missing chart labels without changing numeric values; use ISINs to distinguish securities with the same name.
- Preserve published daily aggregates for unchanged trade groups so adding an ISIN cannot reorder old equal-time trades and alter unrelated prices; recalculate changed groups and subsequent rolling baselines.
- Show the successful refresh time separately from the latest trade date, invalidate changed-file caches, and warn when the refresh is overdue or unverified.
- Gate container releases with tests, retain source/digest receipts, and suspend unsafe package deletion that can break multiarchitecture rollback images.

**Status:** local implementation and verification; GitHub, hosted applications, and partner deployments have not been changed. See the [incident record](docs/incidents/2026-10-12-pipeline-recovery.md) for evidence and open rollout checks, and the [operating guide](docs/OPERATIONS.md) for recovery and maintenance.
