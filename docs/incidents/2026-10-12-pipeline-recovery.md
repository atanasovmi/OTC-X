# Pipeline recovery — 2026-10-12

**Owner:** repository maintainer. **State:** local patch verified; online rollout pending. This is an operational reliability incident, with no evidence of lost published history from the failed jobs.

Local implementation revision: `5a12a3e99550f7a4d101a6066b12e2b4f0892ce4`, branch `fix/durable-pipeline-recovery`. The documentation is a separate reviewable commit. Neither commit has been pushed.

## Impact and evidence

The daily workflow stopped during preflight tests, before collection or publication. The last inspected published data was dated 2026-10-09 at source revision `c086e3bb2e7e9f80db78421c2b29e790c7b60e54`. The separate Windows folder deletion error concerned local ACLs, not remote repository access.

| Date | Evidence |
| --- | --- |
| Oct 9 | [Successful daily run 37924592232](https://github.com/atanasovmi/OTC-X/actions/runs/37924592232): 118 tests passed; Narwhals 2.26.0. |
| Oct 10 | [Failed run 38046433654](https://github.com/atanasovmi/OTC-X/actions/runs/38046433654): treemap test failed; Narwhals 2.27.1. |
| Oct 11 | [Failed run 38134371987](https://github.com/atanasovmi/OTC-X/actions/runs/38134371987): same preflight failure. |
| Oct 12 | [Failed run 38249981608](https://github.com/atanasovmi/OTC-X/actions/runs/38249981608): same failure investigated. |

The traceback reaches Plotly's treemap grouping through Narwhals into pandas: a sector-label aggregation compares text with a floating missing-value sentinel. pandas remained 2.3.3; a floating indirect Narwhals dependency changed without a repository change. Missing historical metadata made the chart vulnerable to that aggregation behavior.

A controlled local A/B test confirmed the cause: the original treemap passes under Narwhals 2.26.0 and fails under 2.27.1 with the same pandas version, remaining dependency graph and Parquet file (SHA-256 `d97475b70cabb6aa740856fdaa6efa40b94b96ce7a2c6b1936f118c6a39f79b7`). The repaired treemap passes both versions; all 51 frontend tests also pass with the previously failing version overlaid in an isolated environment.

The inspected snapshot contains 239 active source listings, 245 retained raw CSV identities, 146,400 master trades and 79,378 daily metric rows for 227 traded ISINs. Six traded historical ISINs have left the current source universe; joining only current metadata lost their names/sectors. Their last known labels were recovered offline from repository commit `752a434`, and recorded in the new registry as inactive. Eighteen active listings have no retained trades and must not appear as assessed/clean.

## Corrective design

The [change log](../../CHANGELOG.md) records the resulting behavior. Dependency pins remove unreviewed version drift; display labels are normalized on copies; treemap identities use ISINs. A persistent listing registry separates current membership from retained history. Validated staged ETL, failing exit codes and pre/post-test publication gates protect the last good snapshot. Refresh clocks/cache signatures expose stale or unverified data. Tested container releases and retained digests support rollback.

The existing formulas, 26-column metric schema and full-history loader interface are retained. No existing historical snapshot is intentionally rewritten by the code patch. The Docker snapshot model remains unchanged and requires explicit partner rollout.

The wider review found a second integrity issue: an unstable sort could reorder same-minute trades when new rows/ISINs were added, changing unrelated old opening/closing prices and anomaly flags. The orchestrator now supplies a validated prior snapshot; unchanged raw groups retain their published daily aggregates, changed/new groups use stable source-order ties, and the complete rolling series is recalculated. Backdated additions may correctly affect subsequent baselines for that ISIN.

## Verification and follow-through

Local verification results and any limitations are recorded here before handoff. The Python 3.12/3.14 execution matrix, actual Docker build and hosted deployment must still run in their target environments; wheel compatibility alone is not execution proof.

| Check | State / evidence |
| --- | --- |
| Full pinned local suite, snapshot validation, frontend all-tab checks | **216 passed**, Python 3.13.7 on Windows. All four tabs render against the retained snapshot and lifecycle fixtures. 29 existing pytest/BDD deprecation warnings; review during future test dependency upgrades. |
| Raw/master and recomputed numeric metric parity | **Passed:** all 245 raw CSVs reconcile to 146,400 trades; 79,378 metric rows and all 26 columns retained. Prices/flags/scores are exact; floating differences at most `5.7e-14`. Adding a synthetic new ISIN/day also preserves unrelated historical signals. |
| Exact known-good dependency installation / `pip check` | Passed in isolated Python 3.13 environment. |
| Binary dependency resolution, Linux amd64/arm64, Python 3.12/3.13/3.14 | Passed all six targets; target execution remains pending. |
| Controlled old-chart dependency regression / repaired-chart check | **Passed:** original fails only with 2.27.1; repaired charts/frontend pass 2.26.0 and 2.27.1. |
| Publication rollback and numerical integrity | **Passed:** real offline stage-chain success/failure, nonzero stage exits, locked-folder restoration, log persistence, registry lifecycle, backdated baseline recalculation, raw totals/extrema/volatility/off-book reconciliation and derived formula checks. |
| Workflow and container promotion checks | **Passed offline:** four workflow files, 19 shell scripts and inline Python syntax; four candidate sign/verify/promotion success/failure simulations. `actionlint` 1.7.12 requires an explicit exception for the newer official `queue: max` field. |
| Push/PR, target matrix, merge and first refresh | Pending owner rollout instruction. |
| Hosted Python/source revision and all four hosted tabs | Pending live inspection. |
| Two consecutive scheduled daily runs | Pending; add run links and refreshed timestamps. |
| Container build/sign/digest and partner rollout | Pending; local Docker daemon unavailable. |

For closure, fill the pending rollout rows with exact source/data revisions, workflow links, deployed digest and timestamps. Record any reviewed source-history correction separately. Use the [operating guide](../OPERATIONS.md) for reproduction and rollback; avoid recording credentials or bulk market data in this incident note.

Reproduction evidence remains in the local ignored `full-project-review/dependency-ci/` directory (integrated JUnit receipt, dependency resolution reports, controlled A/B outputs and promotion simulations). The versioned results above are the review record; CI will retain fresh execution artifacts when the patch is published.
