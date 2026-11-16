# Firefly Development Process

Team 4, ECE 49595 Senior Design. This document is the single source of truth
for how we branch, review, merge, and organize the repo.

## a. Repository Architecture

```
repo/
 ├── CLAUDE.md                    agent/assistant context for this repo
 ├── Firefly Software Development Plan.pdf   the SRS
 ├── doc/                         dev-process.md, api-contract.md, diagrams, spike findings
 ├── client-windows/              WPF desktop app (C#, .NET 8) (planned, not yet created)
 │    ├── src/Firefly.Client/          overlay, trail + ring rendering, screen capture, API client
 │    └── tests/Firefly.Client.Tests/  xUnit
 ├── backend/                     grounding API (Python; AWS Lambda handler + local dev server)
 │    ├── src/app.py                   Lambda handler, Gemini prompt, response validation
 │    ├── template.yaml                SAM template (deploys backend/src/app.py)
 │    └── tests/                       pytest
 ├── mock-frameworks/             stub JSON responses matching the API contract (planned, not yet created)
 ├── .github/workflows/ci.yml, .github/pull_request_template.md
 ├── .gitignore, README.md
```

| Path | What lives here |
|---|---|
| `CLAUDE.md` | Context file for AI coding assistants working in this repo |
| `Firefly Software Development Plan.pdf` | The SRS (SYS/FR/NFR requirements, deliverables) |
| `doc/` | Process docs, the API contract, diagrams, and write-ups from spikes |
| `client-windows/src/Firefly.Client/` | (Planned) WPF overlay, trail/ring rendering, screen capture, grounding-API client |
| `client-windows/tests/Firefly.Client.Tests/` | (Planned) xUnit tests for the client |
| `backend/src/app.py` | Lambda handler: Gemini prompt construction, response validation |
| `backend/template.yaml` | SAM template deploying `backend/src/app.py` |
| `backend/tests/` | pytest tests for the backend |
| `mock-frameworks/` | (Planned) stub JSON responses matching `doc/api-contract.md`, used in mock mode |
| `.github/workflows/ci.yml` | CI pipeline (client build/test, backend lint/test, secret scan) |
| `.github/pull_request_template.md` | Required PR template |
| `.gitignore` / `README.md` | Standard repo root files |

**References:**
- [.NET: Organizing and testing projects with the .NET CLI](https://learn.microsoft.com/en-us/dotnet/core/tutorials/testing-with-cli): Microsoft's guidance for `src/`+`tests/` solution layout, the planned basis for `client-windows/`.
- [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/): why `backend/src/` stays a flat module for now instead of a package, matching the SAM `Handler: app.lambda_handler` path of the deployed Lambda.
- [GitHub Docs: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes): repository structure and README conventions.

## b. Branching / Workflow Model

**GitHub Flow.** No forks. Everyone branches directly inside the team repo.

| Branch | Purpose | Who can merge into it |
|---|---|---|
| `main` | Holds production-ready code matching our final deployment packages (Deliverables 1 & 2). Protected, no direct pushes. | Any teammate, only after an approved PR. |
| `feature/<issue#>-name` | Isolated development for a specific sub-task | The PR author, after receiving approval. |
| `fix/<issue#>-name` | Bug fixes for issues found in a feature that already PR'd into `main` | The branch author, after approval from the original PR's reviewers. |
| `docs/<issue#>-name` | API contracts, workflow definitions, and other process docs (e.g. this file) | Any team member, after review from the whole team. |
| `spike/<name>` | Time-boxed research/experimenting | Never merged. Findings get written up and land in `/doc` via a separate `docs/` PR. |

**Naming convention:** `<type>/<issue#>-short-kebab-name`
Example: `feature/6-trail-animation`

**Commit messages** start with the issue number:
`#6 Add bezier path for trail`

**`main` is the integration/release branch.** Every merged PR lands on `main`,
and it must always build and be demo-ready. Demos are marked with a git tag
(e.g. `demo-2026-11-15`) rather than a separate release branch. There is no
long-lived `release/*` line.

## c. Code Development & Review Policy

- Every change goes through a PR linked to an issue (`Closes #N`).
- At least **1 approval** from someone other than the author. The PR's own author may not approve it.
- Changes to `doc/api-contract.md` or request/response models need **2 approvals**: one client-side reviewer, one backend-side reviewer.
- **Squash merge** only.
- Checks run in this order before merge: **linter → build → tests**, plus a **secrets scan** (gitleaks), all in GitHub Actions. All must pass.
- **1-2 PRs per person per week**. Aim for **< 400 changed lines** per PR; open drafts early rather than batching a huge PR.
- Reviewers respond within **48 hours**.
- AI-generated code follows the same rules as human-written code. The PR description includes a short statement of what an AI tool wrote.
- Secrets (e.g. the Gemini API key) are **never committed**. Use environment variables / a gitignored `.env`.
