# Operating the OTC-X pipeline

The live dashboard runs on Streamlit Community Cloud. Cloud monitors the connected GitHub repository and branch and automatically copies committed code and data; changes to `requirements.txt` trigger dependency installation. The documented production branch is `main`, with `frontend/app.py` as the entrypoint. Keep that existing app configuration and URL.

The daily GitHub workflow collects data, computes metrics, and publishes one validated data commit. The dashboard reads those files; merging application code alone does not collect new trades. To recover missed daily updates, merge the tested patch and dispatch the existing daily workflow once. Its data commit is then automatically picked up by Streamlit. Dashboard users continue using the same URL.

## Data and listing contract

| Artifact | Contract |
| --- | --- |
| `securities.csv` | Complete current source universe; original four columns remain unchanged. |
| `security_registry.csv` | Persistent ISIN identity, last known nonblank name/sector/Valor, Boolean `is_active`. Removal marks inactive; reappearance reactivates. |
| `trades/*.csv` and `master_trades.parquet` | Historical trades retained, including inactive ISINs. Downloads use source ISINs and validate content before replacement. |
| `daily_metrics.parquet` | Original 26 columns and formulas; one ISIN/date row. Historical metrics retain registry metadata. |
| `refresh_status.json` | UTC successful refresh clock and latest trade date, written after the publication gates pass. |

Current market and risk views exclude inactive listings. Historical views/exports keep them. New listings without trades appear as **No trading data**, with no invented metrics. **Clean** requires observations in the dashboard's last 30 observed market dates; old/untraded listings are unassessed. Per-security quantitative baselines still use that security's last 30 trading days.

API pagination must be complete and consistent before listing statuses change. Empty/404 exports are counted separately and preserve prior history. Network failures, malformed exports, zero valid downloads, or exports removing/changing retained trades fail the refresh. Source corrections need an explicit reviewed reconciliation; do not bypass the guard or hard-delete history.

Equal-time trades need a defined order. The orchestrator validates the published baseline and retains its daily aggregates when the underlying trade group is unchanged. New/changed groups use stable source order for ties. All rolling formulas run again over the merged daily series: a newly supplied backdated trade can legitimately change that security's following baselines/flags; adding another ISIN cannot perturb unrelated historical prices.

## Normal refresh and failed jobs

The workflow order is locked install / `pip check` → preflight tests → published-baseline validation → staged ETL → snapshot validation/install → post-refresh tests → validation/status stamp → scoped commit/push. A failure before publication leaves GitHub's previous data intact. Concurrent refreshes are serialized; a non-fast-forward push fails instead of merging untested revisions.

1. Read the failing stage and download the Actions **refresh-receipts** artifact (30-day retention), including install/test/validation logs. Successful runs also commit the pipeline receipt under `backend/logs/`.
2. Check the app's successful refresh time and trade date separately. A weekend may have a recent refresh and an older trade date. Missing/invalid timestamps show unverified freshness; over 36 hours shows overdue freshness.
3. Reproduce in a disposable checkout with the committed pins. Fix the underlying dependency/source/schema issue, then rerun the same gates. Link receipts in the recovery pull request; preserve evidence needed longer than 30 days in a retained internal archive.

GitHub schedules are best effort; `05:00 UTC` is a requested start time, not a service-level guarantee. The freshness warning requires someone to view the app; it is not an independent notification service. Operators should check failed Actions notifications and the two scheduled runs after each recovery.

For an authorized manual refresh in a disposable checkout, run these commands sequentially and stop on any failure:

```text
python -m pip install --only-binary=:all: -r requirements-dev.txt
python -m pip check
python -m pytest tests/ -q
python -m backend.pipeline
python -m pytest tests/ -q
python -m backend.validation --write-refresh-status
```

The orchestrator alone installs a validated local candidate but does not stamp a successful refresh. The final status command must follow tests. Review the resulting diff before any Git publication; GitHub/live publication requires the owner's rollout instruction.

## Rollout and rollback

Before rollout, record the current `main` source/data revision as the rollback reference. Keep the existing Streamlit app URL, repository/branch configuration and Python runtime. The production approval covers the reviewed merge and one controlled data refresh; Community Cloud performs the app update automatically.

1. Publish the reviewed patch branch and inspect Python 3.12/3.13/3.14 CI results. Branch protection is a separate repository setting; new checks alone do not enforce it. Any future rule must accommodate the scoped daily bot writes.
2. After owner approval, merge the tested PR into `main`. Streamlit picks up the code and resolves the changed dependency file automatically; allow that installation to finish.
3. Dispatch **OTC-X Daily Pipeline** once on `main`; wait for all stages, post-refresh tests, validation and the data/status commit to succeed. Streamlit picks up the committed data automatically.
4. Inspect all four hosted tabs, history/export access, inactive/new-listing states, and refresh clocks. Record the merge revision, successful run/data commit and UI result in the recovery PR. Keep the incident in Monitoring until two scheduled refreshes have succeeded.

Roll back a failed Cloud application update using a reviewed revert on top of current data; Streamlit also picks up that corrective commit automatically. Preserve the tested dependency closure when reverting application behavior. For bad data, restore the complete previously validated `backend/data/` snapshot together; do not mix old metrics with new registry/raw files. Preserve any new raw history from the failed candidate before a deliberate data restoration. Revalidate and keep the failure receipt.

## Optional container distribution

Docker is an alternative distribution path, not a prerequisite for updating the live Cloud dashboard. A container contains the source and data from its build and requires explicit image replacement to update. Publishing a GitHub Release or pushing a `v*` tag triggers the container publication workflow; neither is needed for this Cloud recovery.

For an explicitly requested container release, build/sign the tested source, record the image digest and retained `sha-<12-character-source-SHA>` tag, and verify the signature before upgrading an image-based deployment. Roll back that deployment using its recorded known-good digest.

Package cleanup is currently a read-only retention reminder: untagged multiarchitecture child manifests and attestations can be required by tagged images. Do not delete them using a simple untagged-version rule. See [upstream issue 162](https://github.com/actions/delete-package-versions/issues/162).

Use recorded digests for partner upgrades: an older/manual release can move `latest` backward, and tag plus release triggers may build the same revision twice. Builds upload a separate candidate tag, then sign and verify its exact digest before promoting release/rollback tags and `latest` last. A signing failure can leave an unsigned candidate, but cannot advance those release tags. Verify the successful release receipt, digest and signature before deployment.

## Maintenance and documentation

The maintainer reviews dependencies, action SHA pins and the container base monthly, and sooner for relevant security fixes. Update the complete dependency closure in a separate review; run `pip check`, the Python matrix, chart/lifecycle tests and snapshot validation. Verify both container architectures and retain the previous digest. Python pins and a base digest prevent accidental drift; apt packages still follow the base distribution's repository during a new build.

Keep the record small: **GitHub recovery PR** for impact, cause, owner, review, test evidence and rollout checklist; **CHANGELOG** for user-visible behavior; **operating guide** for repeatable procedures. For this Cloud recovery, record the exact merge/data revisions, Actions receipts, UTC refresh time and hosted UI result in the PR; mark the change log as deployed only after verification. Track Prepared → Monitoring → Resolved; merging alone is not recovery. Release notes are optional for a separately requested versioned release, with its source/data versions and image digest where applicable.

The local Windows deletion error was separate: the abandoned outer checkout had a deny ACL for the sandbox identity, while the user's account retained FullControl. Its Git status represented local missing files, not remote deletion. The active patch is in the inner `OTC-X` checkout. Do not commit the outer deletions, change ownership broadly, or use folder deletion to repair CI.

References: [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [concurrency/queue behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#concurrency), [Streamlit automatic code updates](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/edit-your-app), [Streamlit dependency updates](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).
