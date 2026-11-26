"""HTML mínimo das páginas de servidor (login, status da Fase 1). O admin completo é React (Fase 2)."""
from html import escape

_CSS = """
:root{color-scheme:dark;--bg:#0f1115;--card:#181b22;--fg:#e8eaf0;--muted:#9aa3b2;--ok:#3fb950;--warn:#d29922;--err:#f85149;--line:#2a2f3a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 16px}h2{font-size:16px;margin:0 0 12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;margin-bottom:16px}.narrow{max-width:360px;margin:12vh auto}
label{display:block;margin:12px 0}input{width:100%;padding:10px;border-radius:6px;border:1px solid var(--line);background:#0b0d11;color:var(--fg);font:inherit}
button,.btn{display:inline-block;padding:9px 16px;border-radius:6px;border:0;background:#2f81f7;color:#fff;font:inherit;cursor:pointer;text-decoration:none}
.btn.secondary,button.secondary{background:#30363d}table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-top:1px solid var(--line);vertical-align:top}
td:first-child{color:var(--muted);width:38%}.ok{color:var(--ok)}.warn{color:var(--warn)}.err{color:var(--err)}code{background:#0b0d11;padding:2px 6px;border-radius:4px;word-break:break-all}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:space-between}
"""


def page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)} · Kavria</title>"
        f"<link rel='icon' href='/favicon.ico' sizes='any'>"
        f"<link rel='icon' type='image/png' sizes='192x192' href='/icon-192.png'>"
        f"<link rel='apple-touch-icon' href='/apple-touch-icon.png'>"
        f"<style>{_CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


def table(rows: list[tuple[str, str]]) -> str:
    """rows: (rótulo, valor HTML já escapado)"""
    return "<table>" + "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"
