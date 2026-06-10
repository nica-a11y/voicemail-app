from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import requests
from datetime import datetime, timedelta, timezone

COMPOSIO_BASE = "https://backend.composio.dev/api/v2/actions"
COMPOSIO_ACCOUNT_ID = "dialpad_madras-deport"


def composio_call(api_key, action, payload):
    resp = requests.post(
        f"{COMPOSIO_BASE}/{action}/execute",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"connectedAccountId": COMPOSIO_ACCOUNT_ID, "input": payload},
        timeout=25,
    )
    result = resp.json()
    return result.get("data") or result.get("response", {}).get("data") or {}


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        call_id = params.get("call_id", [None])[0]
        api_key = os.environ.get("COMPOSIO_API_KEY", "")

        status = 200
        try:
            if not api_key:
                body = json.dumps({"error": "Dialpad is not configured yet."})
                status = 500
            elif call_id:
                data = composio_call(
                    api_key,
                    "DIALPAD_FETCH_CALL_TRANSCRIPT_BY_ID",
                    {"call_id": call_id},
                )
                lines = data.get("lines", [])
                parts = []
                for line in lines:
                    if line.get("type") != "transcript":
                        continue
                    text = (line.get("content") or "").strip()
                    if not text:
                        continue
                    speaker = (line.get("name") or "Caller").strip() or "Caller"
                    parts.append(f"{speaker}: {text}")
                body = json.dumps({"transcript": "\n".join(parts)})
            else:
                cutoff = int(
                    (datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000
                )
                data = composio_call(
                    api_key,
                    "DIALPAD_RETRIEVE_CALL_INFORMATION",
                    {"started_after": cutoff},
                )
                items = data.get("items", [])
                calls = []
                for c in items:
                    ts = c.get("date_started") or c.get("started") or 0
                    try:
                        dt = datetime.fromtimestamp(
                            int(ts) / 1000, tz=timezone.utc
                        ).strftime("%m/%d %I:%M %p")
                    except Exception:
                        dt = "Unknown time"
                    number = (
                        c.get("external_number")
                        or c.get("from_number")
                        or "Unknown caller"
                    )
                    calls.append(
                        {"id": str(c.get("id", "")), "label": f"{dt}  —  {number}"}
                    )
                body = json.dumps({"calls": calls})
        except Exception as e:
            body = json.dumps({"error": str(e)})
            status = 500

        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())
