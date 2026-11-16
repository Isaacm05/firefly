# Firefly Development Process

Team 4, ECE 49595 Senior Design. This document is the single source of truth
for how we branch, review, merge, and organize the repo.

## a. Repository Architecture

```
repo/
 ├── doc/                         dev-process.md, api-contract.md, diagrams, spike findings
 ├── client-windows/              WPF desktop app (C#, .NET 8)
 │    ├── src/Firefly.Client/          overlay, trail + ring rendering, screen capture, API client
 │    └── tests/Firefly.Client.Tests/  xUnit
 ├── backend/                     grounding API (Python; AWS Lambda handler + local dev server)
 │    ├── src/firefly_grounding/       handler, Gemini prompt, response validation
 │    └── tests/                       pytest
 ├── mocks/                       stub JSON responses matching the API contract
 ├── .github/workflows/ci.yml, .github/pull_request_template.md
 ├── .gitignore, README.md
```

| Path | What lives here |
|---|---|
| `doc/` | Process docs, the API contract, diagrams, and write-ups from spikes |
| `client-windows/src/Firefly.Client/` | WPF overlay, trail/ring rendering, screen capture, grounding-API client |
| `client-windows/tests/Firefly.Client.Tests/` | xUnit tests for the client |
| `backend/src/firefly_grounding/` | Lambda handler, Gemini prompt construction, response validation |
| `backend/tests/` | pytest tests for the backend |
| `mocks/` | Stub JSON responses matching `doc/api-contract.md`, used in mock mode |
| `.github/workflows/ci.yml` | CI pipeline (client build/test, backend lint/test, secret scan) |
| `.github/pull_request_template.md` | Required PR template |
| `.gitignore` / `README.md` | Standard repo root files |

**References:**
- [.NET: Organizing and testing projects with the .NET CLI](https://learn.microsoft.com/en-us/dotnet/core/tutorials/testing-with-cli) — Microsoft's guidance for `src/`+`tests/` solution layout, the basis for `client-windows/`.
- [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — why `backend/src/firefly_grounding/` uses a `src/` layout instead of a flat package.
- [GitHub Docs: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) — repository structure and README conventions.

## b. Branching / Workflow Model

**GitHub Flow.** No forks — everyone branches directly inside the team repo.

| Branch | Purpose |
|---|---|
| `main` | Always builds, always demo-ready. Protected, no direct pushes. |
| `feature/<issue#>-name` | New functionality |
| `fix/<issue#>-name` | Bug fixes |
| `docs/<issue#>-name` | Documentation-only changes |
| `spike/<name>` | Time-boxed research/investigation. **Never merged to main.** Findings get written up and land in `/doc` via a separate `docs/` PR. |

**Naming convention:** `<type>/<issue#>-short-kebab-name`
Example: `feature/6-trail-animation`

**Commit messages** start with the issue number:
`#6 Add bezier path for trail`

**`main` is the integration/release branch.** Every merged PR lands on `main`,
and it must always build and be demo-ready. Demos are marked with a git tag
(e.g. `demo-2026-11-15`) rather than a separate release branch — there is no
long-lived `release/*` line.

## c. Code Development & Review Policy

- Every change goes through a PR linked to an issue (`Closes #N`).
- At least **1 approval** from someone other than the author.
- Changes to `doc/api-contract.md` or request/response models need **2 approvals** — one client-side reviewer, one backend-side reviewer.
- **Squash merge** only.
- CI must pass before merge.
- At least **one PR per person per week**. Aim for **< 400 changed lines** per PR; open drafts early rather than batching a huge PR.
- Reviewers respond within **48 hours**.
- Secrets (e.g. the Gemini API key) are **never committed**. Use environment variables / a gitignored `.env`.
