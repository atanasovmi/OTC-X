# OTC-X Security Audit Report

**Date:** 2026-03-28  
**Scope:** Full application — backend pipeline, frontend dashboard, CI/CD workflow  
**Methodology:** Manual code review, static analysis, threat modelling

---

## Overview

The OTC-X application is a read-only financial data pipeline and Streamlit dashboard with **no user authentication, no database, no file upload endpoints, and no REST API**. Data flows one way: external OTC-X API → backend pipeline → Parquet files on disk → Streamlit frontend. The attack surface is narrow.

The most significant class of vulnerability found is **Stored Cross-Site Scripting (XSS)** via unsanitised data rendered with `unsafe_allow_html=True`. Several lower-severity issues were also identified and fixed.

**No hallucinated vulnerabilities** — components without real risk (e.g., the read-only Streamlit dashboard has no auth to bypass) are noted as "not applicable" rather than fabricated.

---

## Findings

### SEC-01 · Stored XSS via Unescaped Data in HTML Tables

| Field | Value |
|---|---|
| **Severity** | **Critical** |
| **Location** | `frontend/operations/components.py:129-136` (`render_market_table`), `frontend/app.py:654-661` (anomaly detail table) |
| **Status** | **Fixed** |

**Description:**  
Security names (`Name`), sector labels (`Sektor`), and ISIN values sourced from the external OTC-X API were interpolated directly into HTML strings rendered via `st.markdown(..., unsafe_allow_html=True)` without HTML-escaping. The `render_native_dataframe` function in the same file correctly used `html.escape()` (imported as `_esc`), but `render_market_table` and the anomaly detail table in `app.py` did not.

**Exploitation Scenario:**  
If the upstream OTC-X API were compromised or returned a crafted security name containing `<script>alert(document.cookie)</script>`, the payload would execute in every user's browser when viewing the Overview or Anomaly Monitor tabs. This is a Stored XSS vector since the data is persisted in the Parquet file and re-rendered on every page load.

**Fix Applied:**  
All data-sourced values interpolated into HTML are now passed through `html.escape()` before insertion.

---

### SEC-02 · Missing HTTP Request Timeout in Securities Crawler

| Field | Value |
|---|---|
| **Severity** | **High** |
| **Location** | `backend/operations/soft_crawl.py:42` |
| **Status** | **Fixed** |

**Description:**  
The `requests.get()` call to the OTC-X API had no `timeout` parameter. Python's `requests` library defaults to waiting indefinitely, which means a DNS resolution hang, a connection stall, or a slow-loris attack on the API server would cause the entire CI pipeline to hang until the GitHub Actions runner is killed (6-hour default).

**Exploitation Scenario:**  
A network issue or upstream API degradation would block the daily scheduled pipeline indefinitely, preventing data updates. In a CI context this wastes runner minutes and could mask real failures.

**Fix Applied:**  
Added `timeout=30` (seconds) to the `requests.get()` call — matching the existing `TIMEOUT = 10` pattern used in `fetcher.py`.

---

### SEC-03 · Bare `except:` Clause Swallows All Exceptions

| Field | Value |
|---|---|
| **Severity** | **Medium** |
| **Location** | `backend/operations/fetcher.py:223` |
| **Status** | **Fixed** |

**Description:**  
A bare `except:` clause (without specifying an exception type) was used when counting lines in downloaded CSV content. This catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit` in addition to regular exceptions, making it impossible to interrupt or terminate the process cleanly during that code path.

**Fix Applied:**  
Changed `except:` to `except Exception:` to preserve interruptibility.

---

### SEC-04 · Full Stack Trace Printed in Production Error Path

| Field | Value |
|---|---|
| **Severity** | **Medium** |
| **Location** | `backend/operations/metrics.py:454-457` |
| **Status** | **Fixed** |

**Description:**  
The `main()` function's generic exception handler imported and called `traceback.print_exc()`, printing full Python stack traces to stdout. Since the pipeline receipt log captures all stdout and is committed to the git repository by CI, this leaks internal implementation details (file paths, library versions, line numbers) into the public repo's commit history.

**Fix Applied:**  
Replaced `traceback.print_exc()` with a single-line error message showing only the exception type and message.

---

### SEC-05 · Log Files Committed to Public Repository via CI

| Field | Value |
|---|---|
| **Severity** | **Low** |
| **Location** | `.github/workflows/automation_pipeline.yml:39`, `.gitignore:59-60` |
| **Status** | **Acknowledged (not fixed — design choice)** |

**Description:**  
The CI workflow runs `git add backend/data/ backend/logs/` and pushes to the repository. The `.gitignore` has an explicit `!backend/logs/*.log` exception to track log files. This means pipeline receipt logs and downloader logs — which may contain internal file paths, timing data, row counts, and security names — are publicly visible in the git history.

**Risk Assessment:**  
For this project (educational, public data from a public API), this is a conscious design decision documented in the codebase. The logs contain no credentials or private data. However, for a production deployment this pattern should be reconsidered — logs should go to a dedicated logging service rather than version control.

---

## Categories Reviewed — No Finding

The following audit categories were checked and found **not applicable or not vulnerable** given the application's architecture:

| Category | Assessment |
|---|---|
| **Authentication & Session Management** | Not applicable — Streamlit app has no auth, no sessions, no login. It serves read-only public market data. |
| **Authorization & Access Control** | Not applicable — no user roles, no privileged actions, no multi-tenancy. |
| **Secrets & Configuration** | No hardcoded API keys, tokens, or credentials found. The application uses only public, unauthenticated API endpoints. No `.env` files exist. |
| **SQL/NoSQL Injection** | Not applicable — no database. All data is read from local Parquet/CSV files. |
| **Command Injection** | No use of `eval()`, `exec()`, `subprocess`, `os.system()`, or any shell-command execution found. |
| **File Uploads** | Not applicable — no file upload functionality exists. |
| **Unsafe Deserialization** | No use of `pickle`, `yaml.load`, or similar deserialization of untrusted data. Parquet files are read via pyarrow which is safe. |
| **LLM / Agent Risks** | Not applicable — no LLM or AI agent integration. |
| **Dependency Vulnerabilities** | `requirements.txt` pins no versions (uses latest). This is a risk for reproducibility but not a direct security vulnerability in the current state. |
| **SSRF** | The only outbound HTTP calls go to hardcoded `https://www.otc-x.ch/api/...` URLs. No user-controllable URL parameters exist. |

---

## Summary of Changes

| File | Change |
|---|---|
| `frontend/operations/components.py` | Added `html.escape()` to ISIN, Name, and Sektor values in `render_market_table` |
| `frontend/app.py` | Added `from html import escape as _esc`; escaped ISIN, Name, Sektor in anomaly detail table |
| `backend/operations/soft_crawl.py` | Added `timeout=30` to `requests.get()` call |
| `backend/operations/fetcher.py` | Changed bare `except:` to `except Exception:` |
| `backend/operations/metrics.py` | Removed `traceback.print_exc()` from production error handler |
