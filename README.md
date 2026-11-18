Firefly is a voice-guided highlight system that points at what you need without ever taking control of your device.

A remote helper speaks an instruction over an existing call (Zoom/FaceTime/phone); Firefly resolves the target on screen and renders a highlight, and the learner acts themselves. Firefly never sends synthetic clicks or keystrokes.

See [doc/dev-process.md](doc/dev-process.md) for branching and review conventions.

## Running the prototype

The prototype runs entirely on one Windows machine. The Python **backend** runs as a local server on `http://127.0.0.1:8000` and is the only part that calls Gemini, so the API key never goes into the app. The C# **client** takes a screenshot, sends it to the backend, and draws the highlight. Run them in two terminals. The request/response format is in [doc/api-contract.md](doc/api-contract.md).

### Prerequisites

- Windows 10/11
- Python 3.11+
- .NET 8 SDK: `winget install Microsoft.DotNet.SDK.8` (restart VS Code/your terminal afterwards)
- A Gemini API key

### 1. Backend (terminal 1)

One-time setup (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r src\requirements.txt -r requirements-dev.txt pytest ruff
```

Create `backend\.env` containing your key. `.env` is gitignored, so never commit it.

```
GEMINI_API_KEY=your-key-here
```

Start the server:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python src\app.py
```

Wait for `Firefly grounding API on http://127.0.0.1:8000`. There's no speech-to-text yet, so **type what the helper said into this terminal and press Enter** (e.g. `open the start menu`). The next request from the client uses that instruction.

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### 2. Client (terminal 2)

```powershell
cd client-windows
dotnet build src\Firefly.Client
dotnet src\Firefly.Client\bin\Debug\net8.0-windows\Firefly.Client.dll
```

A Firefly pill appears in the **top-right corner** of the screen. Click it, then click **Start**:

1. It shows "Looking…" while the backend asks Gemini (about 6–10 s).
2. A ring highlights the target, and a trail follows your mouse. **You** click inside the ring; Firefly never clicks for you.
3. For multi-step instructions, it finds the next step after each click, then shows "All done!".

Right-click the pill and choose **Quit Firefly** to close it. Re-run `dotnet build` only after code changes.

> **Smart App Control:** use `dotnet …\Firefly.Client.dll` as above, not `dotnet run`. On Windows 11 with Smart App Control on, `dotnet run` launches the locally built (unsigned) `Firefly.Client.exe`, and Windows blocks it ("Part of this app has been blocked"). Starting the DLL through Microsoft's signed `dotnet.exe` avoids this. **Don't turn Smart App Control off.** On Windows 11 it can't be turned back on without reinstalling Windows.

To point the client at a different backend (e.g. a deployed one), set `FIREFLY_API_URL` before starting it.

### Testing without the client

With the server running, `python scripts\try_live.py` (from `backend\`, with the venv active) prompts for instructions, screenshots your screen, calls the API, and prints where to click. `python scripts\try_gemini.py <screenshot.png> "<instruction>"` runs one Gemini call on a saved image, with no server needed.

### Automated tests

From the repo root:

```powershell
cd backend; pytest; ruff check .; cd ..          # Gemini faked, no API key needed
cd client-windows; dotnet test tests\Firefly.Client.Tests; cd ..
```

### Deployment

Not done yet. `backend/template.yaml` is the AWS SAM template for deploying the same code as a Lambda behind API Gateway. The client would then use `FIREFLY_API_URL` to point at it.

## Team

- Isaac Mei
- Nate Brodie
- Natalia Hombs
- Alan Yee