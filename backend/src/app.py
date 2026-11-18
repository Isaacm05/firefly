"""Grounding API: POST /plan and POST /locate (see doc/api-contract.md).

Run locally for the client to call (no AWS needed):

    python src/app.py                 # serves http://127.0.0.1:8000

While it runs, type an instruction into the terminal and press Enter: the next /plan
uses it in place of whatever instruction the client sent (no speech-to-text yet).

`handle()` holds all the logic so the same code can later be deployed as the
AWS Lambda via `lambda_handler`, which keeps the API key off client machines.
"""
import base64
import binascii
import json
import logging
import os
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from create_instructions import create_instructions
from highlight_button import locate_button
from targets import Step

log = logging.getLogger("firefly.api")


class BadRequest(Exception):
    """The request body is malformed; becomes a 400 response."""


def _target_json(target):
    return asdict(target) if target is not None else None


def _image(body):
    try:
        image = base64.b64decode(body["image"], validate=True)
    except (KeyError, TypeError, binascii.Error):
        raise BadRequest("'image' must be a base64-encoded JPEG or PNG") from None
    if not image:
        raise BadRequest("'image' is empty")
    return image


def _plan(body):
    instruction = body.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise BadRequest("'instruction' must be a non-empty string")
    image = _image(body)
    try:
        steps, target = create_instructions(image, instruction.strip())
    except Exception as e:  # noqa: BLE001 -- any Gemini failure becomes a clean error status
        is_timeout = "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower()
        log.warning("[plan] gemini failed: %r", e)
        return (504, {"error": "timeout"}) if is_timeout else (502, {"error": "model_error"})
    finally:
        del image  # NFR-03: screenshot lives only as long as the call
    return 200, {"steps": [asdict(s) for s in steps], "target": _target_json(target)}


def _locate(body):
    step = body.get("step")
    if not (isinstance(step, dict) and isinstance(step.get("label"), str)
            and isinstance(step.get("instruction"), str)):
        raise BadRequest("'step' must have string 'label' and 'instruction'")
    image = _image(body)
    try:
        # locate_button already fails safe (timeouts/errors -> None, i.e. no highlight)
        target = locate_button(image, Step(step["label"], step["instruction"]))
    finally:
        del image
    return 200, {"target": _target_json(target)}


ROUTES = {"/plan": _plan, "/locate": _locate}


def handle(path, raw_body):
    """Route one request. Returns (status code, JSON-serializable dict)."""
    route = ROUTES.get(path.rstrip("/"))
    if route is None:
        return 404, {"error": "not_found"}
    try:
        body = json.loads(raw_body or b"")
        if not isinstance(body, dict):
            raise BadRequest("body must be a JSON object")
        return route(body)
    except (BadRequest, json.JSONDecodeError) as e:
        return 400, {"error": "bad_request", "detail": str(e)}


def lambda_handler(event, context):
    """AWS entry point (API Gateway proxy event). Not used for local runs."""
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw)
    status, payload = handle(event.get("path", ""), raw)
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload)}


# Stand-in for speech-to-text during local demos: the last instruction typed into this
# terminal replaces the one the client sends to /plan. Local server only, never on Lambda.
_typed = {"instruction": None}


def _read_typed_instructions():
    print("Type what the helper said and press Enter (used by the next /plan):", flush=True)
    while True:
        try:
            line = input().strip()
        except EOFError:  # no terminal attached (e.g. started in the background)
            return
        if line:
            _typed["instruction"] = line
            log.info("[prompt] next /plan will use: %r", line)


def _with_typed_instruction(path, raw):
    typed = _typed["instruction"]
    if typed is None or path.rstrip("/") != "/plan":
        return raw
    try:
        body = json.loads(raw or b"")
    except json.JSONDecodeError:
        return raw  # let handle() report the 400
    if not isinstance(body, dict):
        return raw
    body["instruction"] = typed
    return json.dumps(body).encode()


class _LocalHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = _with_typed_instruction(self.path, self.rfile.read(length))
        status, payload = handle(self.path, raw)
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # one short line per request, never the body
        log.info("[http] %s", fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    port = int(os.getenv("PORT", "8000"))
    # 127.0.0.1 only: reachable from this computer, not from the network
    server = ThreadingHTTPServer(("127.0.0.1", port), _LocalHandler)
    log.info("Firefly grounding API on http://127.0.0.1:%d  (POST /plan, POST /locate)", port)
    threading.Thread(target=_read_typed_instructions, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
