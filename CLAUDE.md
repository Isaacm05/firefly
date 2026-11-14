# Firefly

Purdue ECE 49595 SD (senior design) capstone, Team 4. Voice-guided highlight system: a **helper** speaks an instruction, the app resolves the target and renders a highlight — on a screen, a physical object, or eventually in AR — and the **learner** acts themselves. The app never takes control (no synthetic clicks/keystrokes, ever). Product framing is a helper guiding a learner over an existing call (Zoom/FaceTime/phone); building a new calling platform is explicitly out of scope.

## Team 4 (Team Contract, signed 2026-09-04)

- Natalia Hombs — signal/image processing, networking, embedded systems
- Isaac Mei — system design, low-level programming, networking/server systems, zero-copy data streaming w/ Apache (repo owner)
- Nate Brodie — chip/semiconductor design, embedded systems, C
- Alan Yee — hardware architecture, audio signal analysis, semiconductor manufacturing

No formal per-person role titles — expertise areas only. Actual capability/role split lives in the team-split doc (Claude artifact, not in-repo).

## Architecture

One shared instruction pipeline across three capabilities (not sequential "stages"), with a single AWS Lambda + API Gateway backend as the sole caller of the Gemini API — keeps the key off every distributed client. Scaffold lives in `backend/` (SAM template + Lambda handler), shared by Capability 1 and 2.

### Capability 1 — Windows screen guidance (current build target)

- C#/WPF app
- GDI screen capture (`System.Drawing`/`CopyFromScreen` — not `Windows.Graphics.Capture`, overkill for one-shot screenshots)
- Local audio pipeline: NAudio/WASAPI → AEC → RNNoise → Silero VAD → Whisper.net/whisper.cpp streaming
- Rule-based instruction-boundary detection
- Instruction + screenshot sent to the backend's Gemini multimodal grounding call (single-pass vision-language grounding, **not** RAG)
- Returns `{x, y, label, confidence}`, reverse-mapped through resize/DPI to real pixels, rendered via a WPF overlay (transparent/click-through/always-on-top)

**Multi-monitor** (recommended, not yet confirmed by user as of 2026-09-25): capture each display separately (labeled), send all to the grounding model, have it specify screen index in its response. Pattern borrowed from competitor Clicky (see below).

### Capability 2 — Physical objects via camera

- **Target platform: iPhone** (confirmed 2026-09-18, not platform-agnostic)
- **Client framework: React Native** (decided 2026-09-25)
- Does **not** share a codebase with Capability 3 — Capability 3 stays on HoloKit X (Unity/C#, confirmed via its own SDK docs), and React Native has no HoloKit binding. Capability 3 is a separate, later track.
- **Open decision, unresolved:** local object tracking via custom OpenCV (ORB/SIFT detect + CSRT/KCF track) vs. Apple's built-in ARKit object tracking (`ARReferenceObject`/`ARImageTrackingConfiguration`). Both require a custom native-bridge Swift module from React Native either way. Decide during prototyping.
- No per-instruction cloud call for tracking either way. STT moves to the same AWS Lambda backend.
- **Discrepancy, unresolved (2026-11-14):** one team member's individual-skill deliverable describes a working Flutter prototype (`speech_to_text`, "Hey Firefly" wake word, repo `github.com/bobthebestbuilder/hey_firefly`) for the mobile client — conflicts with the React Native decision above. Unclear if superseded or if RN isn't actually final team-wide. Confirm before building against either assumption.

### Capability 3 — AR glasses (final-form target for the proposal's Solution Description)

- Target hardware: **HoloKit X ($129)** — open-source, optical see-through, Unity/C# SDK on ARFoundation (wraps ARKit+ARCore, free 6DOF world tracking, no partner gating)
- Meta Ray-Ban Display ($799, gated WDAT preview) is a documented fallback/aspirational path, not the near-term target

## Backend (`backend/`)

AWS SAM app: `template.yaml` defines a single Lambda (`src/app.py`) behind API Gateway at `POST /ground`. Currently implements the instruction-decomposition call from `prototype/gemini_instructions.py` (comma-separated step list), not yet the per-step grounding call that returns pixel coordinates — that response schema is still an open question (see below). `GEMINI_API_KEY` is a SAM parameter (`NoEcho`), injected as a Lambda env var — never shipped to clients.

## Compound instructions & privacy (NFR-03)

One utterance like "log into the portal" decomposes into an ordered step list; each step is grounded against a fresh screenshot. Advancing to the next step is detected via a **passive, observe-only global input hook** — detects that a click/keypress occurred, never reads/stores/transmits content (a step may be typing a password).

NFR-03 (formalized in the SRS): all captured audio/screenshots/webcam frames stay in RAM only and must be overwritten/freed within 2s of coordinates being returned. Zero raw audio or image files ever written to disk.

## Gemini call prototype (`prototype/gemini_instructions.py`)

Verified speed fixes applied (2026-09-25/26): resize screenshot to 1568px longest side before encoding, reuse one `genai.Client` at module load instead of per-call, `thinking_config.thinking_budget=0`, model `gemini-3.8-flash`. `stream_instructions()` streams the response and yields each button label as soon as its comma is hit.

**Open perf mystery, unresolved (2026-09-26):** user reports 30-60s observed latency even after the above fixes — abnormal for a Flash-tier call with a small image and short output. Leading suspicion: silent SDK retries/backoff on a transient error. Debug logging + timing checkpoints added to the prototype to diagnose; waiting on real numbers.

**Open design question, unresolved (2026-09-26):** does Firefly show a visible label/text near the pointer, or stay pointer-only/silent? Firefly currently has no response-text surface (silent, pointer-only by design), so `label` in the grounding schema is diagnostic-only for steps that already have coordinates, and only load-bearing for future steps that don't. Decide before finalizing the response schema — this is a product-behavior change, not just a schema detail.

## SRS

`Firefly Software Development Plan_.docx` (in the "Team Assignments" Google Drive export, not committed — see `.gitignore`): formal SYS-01..09 scope items, FR-01..15 + NFR-01..05 requirements, 5 deliverables (D1 Windows installer, D2 accessibility/privacy audit, D3 containerized vision pipeline, D4 latency/accuracy benchmark, D5 user guide + dev docs). Confirms iOS/Android/AR glasses are all still formally "Under Evaluation," not committed scope, despite HoloKit X being named as the Capability 3 target elsewhere.

## Competitive analysis: Clicky/HeyClicky

`github.com/farzaa/clicky`, heyclicky.com — macOS menu-bar app, push-to-talk (not ambient/no-trigger like Firefly — a real differentiator, harder problem). Screenshot + transcript → Claude (not Gemini) → streamed SSE response with embedded `[POINT:x,y:label:screenN]` tags parsed mid-stream for perceived speed. Cloud STT (AssemblyAI, Apple Speech fallback) — opposite of Firefly's local-first whisper.cpp. Uses a Cloudflare Worker proxy for all 3 API keys — independent validation of Firefly's own Lambda+API Gateway pattern. Marketing mentions an autonomous "agent mode," unconfirmed in the open-source repo's own architecture doc — don't cite without a better source.

## Current state (2026-11-14)

- `backend/` scaffolded (SAM template + Lambda handler + test), no deployment yet
- `prototype/gemini_instructions.py` exists standalone, not yet wired into the backend's Lambda handler beyond the ported decomposition logic
- No Windows/iOS client code yet
- 30 GitHub issues filed (labeled by capability + role: audio, vision, orchestration, cv-tracking, integration, infra)
- Team-split doc and a C4 System Context + Container diagram published as Claude artifacts, not in-repo
- ECE 49595 Project Proposal in progress (Solution Description drafted: overview, complexity, innovation, ABET factors, system requirements)
