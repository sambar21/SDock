"""A readable page for when the app cannot start because its settings are wrong.

Without it, a host such as Vercel shows only a blank "function failed" page, and the real
reason sits in a log. Only variable names and set/not-set are shown here, never values.
"""
import html
import os

from fastapi.responses import HTMLResponse

# (name, what it is for)
CHECKED = [
    ("DATABASE_URL", "Postgres connection string. Needed on Vercel."),
    ("AUTH_DISABLED", "Set to true for the open demo with no sign-in."),
    ("SECRET_KEY", "Needed only when sign-in is on. 32 or more characters."),
    ("CRON_SECRET", "Optional. Lets Vercel Cron call the sweep endpoint."),
]


def problem_page(message: str) -> HTMLResponse:
    rows = "".join(
        f"<tr><td><code>{name}</code></td><td>{'set' if os.getenv(name) else '<b>not set</b>'}</td>"
        f"<td>{html.escape(use)}</td></tr>"
        for name, use in CHECKED
    )
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Setup needed</title>
<style>
  body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 680px; margin: 48px auto; padding: 0 16px; color: #1c2027; background: #f6f7f9; }}
  .card {{ background: #fff; border: 1px solid #dde1e7; border-radius: 10px; padding: 20px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  td {{ padding: 6px 8px; border-top: 1px solid #dde1e7; vertical-align: top; }}
  code {{ background: #eef0f4; padding: 1px 5px; border-radius: 4px; }}
  .why {{ background: #fde3e1; color: #7a1a14; padding: 10px 12px; border-radius: 8px; }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #e8eaee; background: #14161a; }} .card {{ background: #1d2026; border-color: #2c313a; }}
    td {{ border-color: #2c313a; }} code {{ background: #2c313a; }} .why {{ background: #4a1a17; color: #ff9a93; }}
  }}
</style></head>
<body><div class="card">
<h1 style="margin-top:0">Setup needed</h1>
<p class="why">{html.escape(message)}</p>
<p>The app did not start because its settings are incomplete. On Vercel, open
<b>Settings, then Environment Variables</b>, add what is missing for the <b>Production</b> environment,
then <b>redeploy</b>. Existing deployments do not pick up new values.</p>
<table>{rows}</table>
</div></body></html>"""
    return HTMLResponse(body, status_code=503)
