# 🛡️ Security Policy

<div align="center">

<img src="https://img.shields.io/badge/Security-Policy-B22222?style=for-the-badge&logo=shield&logoColor=white" alt="Security Policy"/>
<img src="https://img.shields.io/badge/License-Proprietary-150458?style=for-the-badge&logo=law&logoColor=white" alt="Proprietary"/>
<img src="https://img.shields.io/badge/Data-Swiss_OTC_Market-009688?style=for-the-badge" alt="Swiss OTC Market"/>

</div>

<br/>

> **This security policy governs the OTC-X Liquidity Intelligence Radar** — a proprietary data pipeline and analytics platform processing Swiss OTC market data under explicit authorization from **Berner Kantonalbank AG (BEKB)**.
>
> All provisions herein are subject to the [Proprietary Notice & Terms of Use](LICENSE.md).

<br/>

---

<br/>

## 📋 Table of Contents

- [Supported Versions](#-supported-versions)
- [Reporting a Vulnerability](#-reporting-a-vulnerability)
- [Security Scope](#-security-scope)
- [Infrastructure Security](#-infrastructure-security)
- [Data Protection & Sovereignty](#-data-protection--sovereignty)
- [Dependency Management](#-dependency-management)
- [Access Control](#-access-control)
- [Incident Response](#-incident-response)
- [Security Best Practices for Contributors](#-security-best-practices-for-contributors)
- [Disclosure Policy](#-disclosure-policy)
- [Acknowledgements](#-acknowledgements)

<br/>

---

<br/>

## ✅ Supported Versions

OTC-X follows a **rolling-release model** on the `main` branch. There are no discrete version releases — the latest commit on `main` is the only supported version.

| Branch / Deployment  | Status | Security Updates |
|:---|:---:|:---:|
| `main` (latest)      | ✅ Active | ✅ Supported |
| Feature branches      | 🔧 Development | ⚠️ Best-effort |
| Streamlit Cloud (live dashboard) | ✅ Active | ✅ Supported |
| Archived commits / forks | ❌ Unsupported | ❌ Not covered |

> **Policy:** Security patches are applied exclusively to the `main` branch and deployed immediately. Users running forked or archived copies do so entirely at their own risk and in potential violation of the [Proprietary Notice](LICENSE.md).

<br/>

---

<br/>

## 🔐 Reporting a Vulnerability

**Do NOT report security vulnerabilities through public GitHub Issues.**

If you discover a security vulnerability in OTC-X, please report it **privately** using one of the following channels:

### Preferred: GitHub Private Security Advisory

1. Navigate to the [**Security Advisories**](https://github.com/atanasovmi/OTC-X/security/advisories) tab of this repository
2. Click **"New draft security advisory"**
3. Provide a detailed description of the vulnerability

### Alternative: Direct Contact

| Channel | Address |
|:---|:---|
| **GitHub** | [@atanasovmi](https://github.com/atanasovmi) (direct message or profile contact) |

### What to Include in Your Report

To help us assess and resolve the issue efficiently, please include:

- **Description** — Clear summary of the vulnerability
- **Location** — Affected file(s), module(s), or endpoint(s)
- **Reproduction** — Step-by-step instructions to reproduce the issue
- **Impact** — Your assessment of severity (e.g., data exposure, unauthorized access, integrity violation)
- **Environment** — Python version, OS, and any relevant configuration
- **Proof of Concept** — Code snippet, screenshot, or log output demonstrating the issue (if available)
- **Suggested Fix** — Optional but appreciated

### Response Commitment

| Milestone | Timeframe |
|:---|:---|
| **Acknowledgement** | Within **48 hours** of receipt |
| **Initial Assessment** | Within **5 business days** |
| **Resolution Target** | Within **30 days** for critical/high severity |
| **Status Updates** | Every **7 days** until resolution |

### After Submission

- Your report will be triaged and assigned a severity level using [CVSS v3.1](https://www.first.org/cvss/calculator/3.1) scoring
- You will receive regular updates on the investigation and remediation progress
- **Accepted vulnerabilities** will be patched, and you will be credited in the [Acknowledgements](#-acknowledgements) section (unless you prefer to remain anonymous)
- **Declined reports** will receive a written justification explaining why the issue does not constitute a vulnerability in this context

<br/>

---

<br/>

## 🎯 Security Scope

### In Scope

The following components are covered by this security policy:

| Component | Description |
|:---|:---|
| **Backend Pipeline** | `backend/pipeline.py`, `backend/operations/*` — ETL stages, API interactions, data processing |
| **Frontend Dashboard** | `frontend/app.py`, `frontend/operations/*` — Streamlit UI, data visualization, CSS injection |
| **Data Layer** | `backend/data/*` — Parquet/CSV files containing OTC-X market data |
| **CI/CD Infrastructure** | `.github/workflows/automation_pipeline.yml` — GitHub Actions daily pipeline |
| **Configuration** | `.streamlit/config.toml`, `requirements.txt` — Runtime and deployment configuration |
| **Streamlit Cloud Deployment** | Live dashboard at `otc-x-radar.streamlit.app` |

### Out of Scope

| Component | Reason |
|:---|:---|
| OTC-X API / otc-x.ch | Owned and operated by Berner Kantonalbank AG — report directly to BEKB |
| Streamlit Cloud platform | Managed by Streamlit Inc. — report to [Streamlit Security](https://streamlit.io/security) |
| GitHub platform vulnerabilities | Report to [GitHub Security](https://github.com/security) |
| Third-party PyPI packages | Report to respective package maintainers (see [Dependency Management](#-dependency-management)) |

<br/>

---

<br/>

## 🏗️ Infrastructure Security

### CI/CD Pipeline (GitHub Actions)

The automated daily pipeline (`automation_pipeline.yml`) follows these security principles:

```
Principle                         Implementation
─────────────────────────────     ─────────────────────────────────────────────
Least-privilege permissions       contents: write — only what's needed to commit data
No secret exfiltration            Pipeline uses no API keys, tokens, or credentials
Immutable runners                 ubuntu-latest — fresh VM per execution
Dependency pinning                actions/checkout@v4, actions/setup-python@v5
Isolated execution                Each run is self-contained, no persistent state on runner
```

### Streamlit Cloud Deployment

| Measure | Implementation |
|:---|:---|
| HTTPS enforcement | All traffic encrypted via TLS (managed by Streamlit Cloud) |
| Read-only data access | Dashboard loads pre-computed Parquet files — no write access to source data |
| No authentication bypass | Dashboard is intentionally public (read-only analytics); no sensitive data exposed |
| Server-side rendering | All data processing occurs server-side; raw data files are not served to the client |

### Repository Security

| Measure | Implementation |
|:---|:---|
| Branch protection | `main` branch is the single source of truth |
| `.gitignore` hardening | Environment files (`.env`, `.venv`), credentials, and IDE configs excluded |
| No hardcoded secrets | Paths resolved dynamically via `Path(__file__).resolve().parent` — no absolute paths or credentials in source |
| Bot-only CI commits | Pipeline commits are made exclusively by `github-actions[bot]` with limited scope (`backend/data/`, `backend/logs/`) |

<br/>

---

<br/>

## 🔒 Data Protection & Sovereignty

This project processes financial market data under explicit authorization. Data handling is governed by the [Proprietary Notice & Terms of Use](LICENSE.md), specifically:

### Data Classification

| Classification | Data Type | Handling |
|:---|:---|:---|
| **Internal** | Raw trade data (`trades/*.csv`, `master_trades.parquet`) | Processed server-side only; committed to repository by CI bot |
| **Internal** | Computed metrics (`daily_metrics.parquet`) | Derived analytics; served read-only via dashboard |
| **Public** | Securities metadata (`securities.csv`) | Publicly available information from OTC-X listings |
| **Restricted** | Pipeline execution logs (`backend/logs/`) | Operational data; committed but not served publicly |

### Data Sovereignty Provisions

As defined in [LICENSE.md — Art. 2](LICENSE.md):

> The author maintains the singular right to process and retrieve data from the Berner Börse (OTC-X). This authorization was granted by Berner Kantonalbank AG and is strictly limited to this project.

**Security implications:**
- No third party is authorized to replicate data streams from this project
- Automated or manual data extraction for storage outside BEKB infrastructure is prohibited
- Using project logic to bypass OTC-X security or access protocols is forbidden

### Anti-Scraping Enforcement

The project includes explicit prohibitions ([LICENSE.md — Art. 3](LICENSE.md)) against:

1. **Cloning and executing** this code in unauthorized environments
2. **Automated data extraction** from the pipeline or dashboard for external storage
3. **Impersonation** of BEKB or OTC-X services using this codebase

> ⚠️ **Violations of data sovereignty provisions will be treated as security incidents** and may result in legal action under Swiss law.

<br/>

---

<br/>

## 📦 Dependency Management

### Current Dependency Stack

| Package | Purpose | Security Relevance |
|:---|:---|:---|
| `pandas` | Frontend data manipulation | Data integrity in analytics layer |
| `numpy` | Numerical computation | Metrics engine calculations |
| `requests` | HTTP client for OTC-X API | Network-facing; handles API communication |
| `polars` | Backend ETL engine (Rust-based) | Memory-safe by design; high-performance data processing |
| `pyarrow` | Parquet serialization | File I/O; deserialization of data artifacts |
| `streamlit` | Dashboard framework | Web-facing; serves the public dashboard |
| `plotly` | Chart rendering | Client-side JavaScript generation |
| `pytest-bdd` | BDD test framework | Development-only; no production impact |

### Dependency Security Practices

- **Minimal footprint** — Only 8 direct dependencies; reduced attack surface
- **No credential-bearing packages** — No database drivers, auth libraries, or cloud SDKs
- **Rust-backed core** — Polars leverages Rust's memory safety guarantees for the ETL pipeline
- **Pip-cached CI** — Dependencies are cached in GitHub Actions to reduce supply-chain exposure during installation
- **Monitoring** — Maintainer monitors [GitHub Dependabot alerts](https://github.com/atanasovmi/OTC-X/security/dependabot) and [PyPI advisories](https://pypi.org/security/) for known vulnerabilities

### Reporting a Dependency Vulnerability

If you discover a vulnerability in one of OTC-X's dependencies:

1. **Check if it's already known** — Review [Dependabot alerts](https://github.com/atanasovmi/OTC-X/security/dependabot)
2. **Report upstream first** — File an issue with the affected package maintainer
3. **Notify us** — Open a [private security advisory](#preferred-github-private-security-advisory) so we can assess impact and update as needed

<br/>

---

<br/>

## 🚪 Access Control

### Repository Access

| Role | Permissions | Scope |
|:---|:---|:---|
| **Owner** ([@atanasovmi](https://github.com/atanasovmi)) | Full admin | All repository settings, code, and data |
| **github-actions[bot]** | `contents: write` | Limited to `backend/data/` and `backend/logs/` commits only |
| **Public viewers** | Read-only | Source code visible per GitHub public repo; execution prohibited per [LICENSE.md — Art. 3](LICENSE.md) |

### Dashboard Access

| Access Level | Description |
|:---|:---|
| **Public** | Read-only analytics dashboard — no login required |
| **No write access** | Dashboard cannot modify source data or pipeline artifacts |
| **No raw data export** | Pre-aggregated visualizations only; raw Parquet files are not downloadable from the dashboard |

### Principle of Least Privilege

- The CI/CD bot has the minimum permissions required (`contents: write`) — no admin, no settings access
- No API keys, tokens, or secrets are stored in the repository
- The OTC-X API is accessed without authentication (public endpoints) — no credential management overhead

<br/>

---

<br/>

## 🚨 Incident Response

In the event of a confirmed security incident, the following response procedure applies:

### Severity Classification

| Severity | CVSS Score | Example | Response Time |
|:---|:---:|:---|:---|
| **🔴 Critical** | 9.0 – 10.0 | Data exfiltration, unauthorized pipeline execution | Immediate (< 24h) |
| **🟠 High** | 7.0 – 8.9 | Supply-chain compromise, credential exposure | < 48 hours |
| **🟡 Medium** | 4.0 – 6.9 | XSS in dashboard, information disclosure | < 7 days |
| **🟢 Low** | 0.1 – 3.9 | Minor information leak, DoS on non-critical path | < 30 days |

### Response Procedure

```
1. IDENTIFY      →  Confirm the vulnerability and assess blast radius
2. CONTAIN       →  Disable affected components (pipeline pause, dashboard takedown if needed)
3. ERADICATE     →  Develop and test the fix on a private branch
4. RECOVER       →  Deploy the patch to main; redeploy dashboard
5. LESSONS       →  Post-mortem documentation; update this policy if needed
6. NOTIFY        →  Inform the reporter and update the security advisory
```

### BEKB Escalation

For incidents involving data sovereignty violations or unauthorized access to OTC-X market data:

- The maintainer will notify BEKB Trading Desk stakeholders directly
- Response will follow both this policy and any applicable BEKB internal security procedures
- Swiss data protection regulations apply

<br/>

---

<br/>

## 📝 Security Best Practices for Contributors

> **Note:** This is proprietary software. Contributions are reviewed on a case-by-case basis per the [Feedback & Ideas](README.md#-feedback--ideas) section.

If your contribution is accepted for review, ensure:

### Code Security

- [ ] **No hardcoded credentials** — Never commit API keys, tokens, passwords, or connection strings
- [ ] **Dynamic path resolution** — Use `Path(__file__).resolve().parent` chains; never hardcode absolute paths
- [ ] **Input validation** — Sanitize all external inputs (API responses, CSV data, user-provided parameters)
- [ ] **Type safety** — Maintain type hints on all functions; enforce with docstrings

### Data Security

- [ ] **No raw data in commits** — Pipeline data artifacts are committed only by the CI bot
- [ ] **Parquet schema validation** — Ensure schema consistency when modifying ETL stages
- [ ] **No PII in logs** — Pipeline logs must contain operational data only, never personal or financial identifiers

### Dependency Security

- [ ] **Minimal dependencies** — Justify any new package addition; prefer stdlib solutions
- [ ] **Pin major versions** — When adding dependencies, specify version constraints in `requirements.txt`
- [ ] **Audit before merge** — Review dependency license compatibility and known CVEs

<br/>

---

<br/>

## 📣 Disclosure Policy

OTC-X follows a **coordinated disclosure** approach:

| Phase | Action | Timeline |
|:---|:---|:---|
| **1. Private Report** | Vulnerability reported via [private advisory](#preferred-github-private-security-advisory) | Day 0 |
| **2. Triage** | Maintainer acknowledges and begins investigation | Day 0 – 2 |
| **3. Fix Development** | Patch developed and tested on private branch | Day 2 – 25 |
| **4. Release** | Fix deployed to `main` and Streamlit Cloud | Day 25 – 30 |
| **5. Advisory Publication** | GitHub Security Advisory published with CVE (if applicable) | Day 30+ |
| **6. Public Disclosure** | Full details released after patch deployment | Day 30 – 90 |

> We kindly request that reporters **refrain from public disclosure** until a fix has been deployed and an advisory published. We commit to resolving confirmed vulnerabilities within **90 days** of the initial report.

<br/>

---

<br/>

## 🏆 Acknowledgements

We value the security research community and recognize those who help keep OTC-X secure.

Confirmed vulnerability reporters will be acknowledged here (with permission):

| Researcher | Vulnerability | Date | Severity |
|:---|:---|:---|:---|
| — | *No reports yet* | — | — |

> If you've reported a vulnerability and would like to be acknowledged, please indicate this in your report. We respect requests for anonymity.

<br/>

---

<br/>

<div align="center">

<sub>This security policy is effective as of <b>March 2026</b> and will be reviewed periodically.</sub>

<br/>

<sub>🇨🇭 Built with precision for the Swiss OTC market — security is not optional.</sub>

<br/><br/>

<img src="https://img.shields.io/badge/▸_Back_to_README-1A1A2E?style=for-the-badge" alt="Back to README"/>

</div>
