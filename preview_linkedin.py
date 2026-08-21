"""Generate a local LinkedIn-style preview for a saved post."""
import argparse
import html
from pathlib import Path

from agents import publisher
from core import db


def _latest_post() -> dict | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM posts ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def _post_by_id(post_id: int) -> dict | None:
    return db.get_post(post_id)


def _paragraphs(text: str) -> str:
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    return "\n".join(f"        <p>{html.escape(chunk).replace(chr(10), '<br>')}</p>" for chunk in chunks)


def _render(post: dict) -> str:
    text = publisher.compose_text(post)
    title = html.escape(post.get("title") or "LinkedIn Preview")
    source_name = html.escape(post.get("source_name") or "")
    theme = html.escape(post.get("theme") or "")
    created_at = html.escape(post.get("created_at") or "")
    body = _paragraphs(text)

    return f"""<!doctype html>
<html lang="kk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f3f2ef;
      --card: #ffffff;
      --text: #191919;
      --muted: #666666;
      --line: #d6d6d6;
      --blue: #0a66c2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Georgia, "Times New Roman", serif;
      display: grid;
      place-items: start center;
      padding: 32px 14px;
    }}
    .shell {{ width: min(100%, 560px); }}
    .note {{
      color: var(--muted);
      font: 13px/1.4 Verdana, Geneva, sans-serif;
      margin: 0 0 12px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
      overflow: hidden;
    }}
    .header {{
      display: grid;
      grid-template-columns: 48px 1fr;
      gap: 10px;
      padding: 14px 16px 8px;
      align-items: center;
    }}
    .avatar {{
      width: 48px;
      height: 48px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: #0f766e;
      color: white;
      font: 700 18px/1 Verdana, Geneva, sans-serif;
    }}
    .name {{
      font: 700 15px/1.25 Verdana, Geneva, sans-serif;
    }}
    .meta {{
      margin-top: 2px;
      color: var(--muted);
      font: 12px/1.35 Verdana, Geneva, sans-serif;
    }}
    .content {{
      padding: 0 16px 10px;
      font: 15px/1.48 Georgia, "Times New Roman", serif;
      white-space: normal;
    }}
    .content p {{ margin: 10px 0; }}
    .source {{ color: var(--blue); word-break: break-word; }}
    .actions {{
      border-top: 1px solid var(--line);
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      color: var(--muted);
      font: 600 13px/1 Verdana, Geneva, sans-serif;
      padding: 4px 8px;
    }}
    .action {{ text-align: center; padding: 10px 4px; }}
    @media (max-width: 480px) {{
      body {{ padding: 12px 8px; }}
      .content {{ font-size: 14px; }}
      .actions {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <p class="note">Local preview only. This is the text that publisher.compose_text() would send to LinkedIn.</p>
    <article class="card">
      <header class="header">
        <div class="avatar">K</div>
        <div>
          <div class="name">KazTech AI</div>
          <div class="meta">Draft preview · {theme} · {source_name}</div>
          <div class="meta">{created_at}</div>
        </div>
      </header>
      <section class="content">
{body}
      </section>
      <footer class="actions">
        <div class="action">Like</div>
        <div class="action">Comment</div>
        <div class="action">Repost</div>
        <div class="action">Send</div>
      </footer>
    </article>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-id", type=int, help="Post id to preview. Defaults to latest post.")
    parser.add_argument("--out", default="linkedin_preview.html", help="Output HTML path.")
    args = parser.parse_args()

    post = _post_by_id(args.post_id) if args.post_id else _latest_post()
    if not post:
        raise SystemExit("No posts found. Run orchestrator.py --dry first.")

    out_path = Path(args.out)
    out_path.write_text(_render(post), encoding="utf-8")
    print(f"Generated {out_path.resolve()}")


if __name__ == "__main__":
    main()