"""Builds the live SVG cards for the profile README.

Pulls public stats from the GitHub GraphQL API and writes, into the output dir:
  card-dark.svg / card-light.svg       neofetch-style terminal card
  repo-<name>-dark.svg / -light.svg    project cards for FEATURED repos

Usage: GITHUB_TOKEN=... python scripts/generate.py <login> <out_dir>
       python scripts/generate.py --mock <out_dir>   (render with sample data)
"""

import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

FEATURED = ["kub_rag", "mcp-server", "docs-agent", "openalgo"]

THEMES = {
    "dark": dict(bg="#0b0820", bg2="#120b2e", border="#2e2363", fg="#e2e8f0", dim="#94a3b8",
                 key="#c4b5fd", accent="#f472b6", ok="#86efac", art="#a78bfa", bar_bg="#1e1b4b"),
    "light": dict(bg="#ffffff", bg2="#f5f3ff", border="#ddd6fe", fg="#1e1b4b", dim="#64748b",
                  key="#6d28d9", accent="#db2777", ok="#15803d", art="#7c3aed", bar_bg="#ede9fe"),
}

FONT = "ui-monospace, SFMono-Regular, 'JetBrains Mono', Menlo, Consolas, monospace"

LOGO = [
    "X.....XXXX.",
    "X.....X...X",
    "X.....X...X",
    "X.....X...X",
    "X.....X...X",
    "X.....X...X",
    "XXXXX.XXXX.",
]

QUERY = """
query($login: String!, $from: DateTime!) {
  user(login: $login) {
    name login createdAt
    followers { totalCount }
    following { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, first: 100, orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name description isFork stargazerCount forkCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
      }
    }
    contributionsCollection(from: $from) {
      totalCommitContributions totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


def fetch(login, token):
    start = dt.datetime(dt.date.today().year, 1, 1).isoformat() + "Z"
    body = json.dumps({"query": QUERY, "variables": {"login": login, "from": start}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]


def mock():
    langs = [("Python", "#3572A5", 60), ("TypeScript", "#3178c6", 25), ("JavaScript", "#f1e05a", 10), ("Shell", "#89e051", 5)]
    repos = [{"name": n, "description": f"Sample description for {n}, which is long enough to wrap onto a second line of the card.",
              "isFork": n != "kub_rag", "stargazerCount": 3, "forkCount": 1,
              "primaryLanguage": {"name": "Python", "color": "#3572A5"},
              "languages": {"edges": [{"size": s, "node": {"name": l, "color": c}} for l, c, s in langs]}}
             for n in FEATURED + ["other"]]
    return {"name": "Lakshya Dubey", "login": "lakshya-byte", "createdAt": "2023-02-14T00:00:00Z",
            "followers": {"totalCount": 42}, "following": {"totalCount": 17},
            "pullRequests": {"totalCount": 64}, "issues": {"totalCount": 12},
            "repositories": {"totalCount": 56, "nodes": repos},
            "contributionsCollection": {"totalCommitContributions": 812, "totalPullRequestContributions": 51,
                                        "contributionCalendar": {"totalContributions": 1024}}}


def uptime(created):
    start = dt.datetime.fromisoformat(created.replace("Z", "+00:00")).date()
    days = (dt.date.today() - start).days
    years, rem = divmod(days, 365)
    months = rem // 30
    return f"{years}y {months}m" if years else f"{months}m {rem % 30}d"


def top_languages(repos, n=6):
    totals = {}
    for r in repos:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            name, color = e["node"]["name"], e["node"]["color"] or "#8b949e"
            size, _ = totals.get(name, (0, color))
            totals[name] = (size + e["size"], color)
    ranked = sorted(totals.items(), key=lambda kv: -kv[1][0])
    total = sum(s for _, (s, _) in ranked) or 1
    top = [(name, color, s / total) for name, (s, color) in ranked[:n]]
    rest = 1 - sum(p for _, _, p in top)
    if rest > 0.005:
        top.append(("Other", "#8b949e", rest))
    return top


def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def card(u, t):
    repos = u["repositories"]["nodes"]
    own = [r for r in repos if not r["isFork"]]
    stars = sum(r["stargazerCount"] for r in own)
    cc = u["contributionsCollection"]
    year = dt.date.today().year
    login = u["login"]

    rows = [
        ("title", f"{login}@github"),
        ("rule", "─" * 30),
        ("OS", "Linux · macOS · whatever ships"),
        ("Uptime", uptime(u["createdAt"])),
        ("Role", "AI Engineer · Full-Stack Dev"),
        ("Shell", "zsh + way too many tmux panes"),
        ("Focus", "RAG · MCP · Agents · LLM infra"),
        ("Stack", " · ".join(n for n, _, _ in top_languages(repos)[:3] if n != "Other")),
        ("", ""),
        ("Repos", f"{u['repositories']['totalCount']}  (★ {stars} on originals)"),
        ("Followers", f"{u['followers']['totalCount']}"),
        (f"Commits {year}", f"{cc['totalCommitContributions']:,}"),
        (f"Contribs {year}", f"{cc['contributionCalendar']['totalContributions']:,}"),
        ("PRs · Issues", f"{u['pullRequests']['totalCount']} · {u['issues']['totalCount']}"),
    ]

    W, H = 900, "__H__"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" font-size="15">',
           "<defs><style>",
           ".r{opacity:0;animation:in .35s ease-out forwards}",
           "@keyframes in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}",
           ".cur{animation:b 1s steps(1) infinite}@keyframes b{50%{opacity:0}}",
           "</style>",
           f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg"]}"/><stop offset="1" stop-color="{t["bg2"]}"/></linearGradient>',
           "</defs>",
           f'<rect x=".5" y=".5" width="{W-1}" height="__H1__" rx="14" fill="url(#g)" stroke="{t["border"]}"/>',
           # window chrome
           '<g transform="translate(24 26)"><circle r="6" fill="#ff5f57"/><circle cx="20" r="6" fill="#febc2e"/><circle cx="40" r="6" fill="#28c840"/></g>',
           f'<text x="{W/2}" y="31" text-anchor="middle" fill="{t["dim"]}" font-size="13">neofetch — {escape(login)}</text>',
           f'<line x1="0" y1="50" x2="{W}" y2="50" stroke="{t["border"]}"/>',
           f'<text x="28" y="82" fill="{t["ok"]}">❯ <tspan fill="{t["fg"]}">neofetch</tspan></text>']

    # pixel logo
    cell, gap, ox, oy = 20, 4, 34, 112
    out.append(f'<g fill="{t["art"]}">')
    for r, row in enumerate(LOGO):
        for c, ch in enumerate(row):
            if ch == "X":
                out.append(f'<rect class="r" style="animation-delay:{(r + c) * 0.035:.2f}s" x="{ox + c*(cell+gap)}" '
                           f'y="{oy + r*(cell+gap)}" width="{cell}" height="{cell}" rx="3"/>')
    out.append("</g>")
    bx0, by0 = ox, oy + len(LOGO) * (cell + gap) + 30
    out.append(f'<g class="r" style="animation-delay:.5s"><rect x="{bx0}" y="{by0}" width="{len(LOGO[0])*(cell+gap)-gap}" '
               f'height="40" rx="8" fill="none" stroke="{t["art"]}" stroke-width="1.5"/>'
               f'<text x="{bx0 + (len(LOGO[0])*(cell+gap)-gap)/2}" y="{by0+26}" text-anchor="middle" fill="{t["art"]}" '
               f'font-weight="700">ship it ▸</text></g>')

    # info rows
    x, y0, lh = 330, 112, 23
    for i, (k, v) in enumerate(rows):
        y = y0 + i * lh
        delay = f"animation-delay:{0.4 + i*0.07:.2f}s"
        if k == "title":
            user, host = v.split("@")
            out.append(f'<text class="r" style="{delay}" x="{x}" y="{y}" font-weight="700">'
                       f'<tspan fill="{t["accent"]}">{escape(user)}</tspan><tspan fill="{t["fg"]}">@</tspan>'
                       f'<tspan fill="{t["accent"]}">{escape(host)}</tspan></text>')
        elif k == "rule":
            out.append(f'<text class="r" style="{delay}" x="{x}" y="{y}" fill="{t["dim"]}">{v}</text>')
        elif k:
            out.append(f'<text class="r" style="{delay}" x="{x}" y="{y}"><tspan fill="{t["key"]}" font-weight="700">{escape(k)}</tspan>'
                       f'<tspan fill="{t["dim"]}">: </tspan><tspan fill="{t["fg"]}">{escape(v)}</tspan></text>')

    # language bar
    by = y0 + len(rows) * lh + 2
    bx, bw = x, W - x - 40
    langs = top_languages(repos)
    d = 0.4 + len(rows) * 0.07
    out.append(f'<g class="r" style="animation-delay:{d:.2f}s">')
    out.append(f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5"/></clipPath>')
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="10" rx="5" fill="{t["bar_bg"]}"/>')
    out.append('<g clip-path="url(#bar)">')
    cx = bx
    for name, color, p in langs:
        w = bw * p
        out.append(f'<rect x="{cx:.1f}" y="{by}" width="{w:.1f}" height="10" fill="{color}"/>')
        cx += w
    out.append("</g>")
    lx, ly = bx, by + 30
    for name, color, p in langs:
        label = f"{name} {p*100:.1f}%"
        step = 22 + len(label) * 8.2
        if lx + step > W - 20:
            lx, ly = bx, ly + 22
        out.append(f'<circle cx="{lx+5}" cy="{ly-5}" r="5" fill="{color}"/>'
                   f'<text x="{lx+15}" y="{ly}" font-size="13" fill="{t["dim"]}">{escape(label)}</text>')
        lx += step
    out.append("</g>")

    # palette blocks + prompt
    py = ly + 40
    pal = ["#ef4444", "#f59e0b", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7", "#ec4899", "#e2e8f0"]
    out.append(f'<g class="r" style="animation-delay:{d+0.15:.2f}s">')
    for i, c in enumerate(pal):
        out.append(f'<rect x="{34 + i*26}" y="{py-14}" width="22" height="14" rx="3" fill="{c}"/>')
    out.append("</g>")
    out.append(f'<text x="{x}" y="{py}" fill="{t["ok"]}" class="r" style="animation-delay:{d+0.25:.2f}s">❯ '
               f'<tspan fill="{t["dim"]}">updated {dt.date.today():%d %b %Y}</tspan> <tspan class="cur" fill="{t["accent"]}">█</tspan></text>')
    out.append("</svg>")
    h = py + 28
    return "\n".join(out).replace("__H1__", str(h - 1)).replace("__H__", str(h))


def repo_card(r, t):
    W, H = 440, 150
    desc = wrap(r["description"] or "No description yet.", 50)[:2]
    lang = r["primaryLanguage"] or {"name": "—", "color": "#8b949e"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
           f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg"]}"/>'
           f'<stop offset="1" stop-color="{t["bg2"]}"/></linearGradient>'
           f'<linearGradient id="e" x1="0" x2="1"><stop offset="0" stop-color="{t["art"]}"/><stop offset="1" stop-color="{t["accent"]}"/></linearGradient></defs>',
           f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="12" fill="url(#g)" stroke="{t["border"]}"/>',
           f'<rect x="1" y="1" width="{W-2}" height="3" rx="1.5" fill="url(#e)"/>',
           f'<text x="22" y="40" font-size="18" font-weight="700" fill="{t["key"]}">'
           f'<tspan fill="{t["dim"]}">📦 </tspan>{escape(r["name"])}</text>']
    if r["isFork"]:
        out.append(f'<text x="{W-22}" y="38" text-anchor="end" font-size="11" fill="{t["dim"]}">⑂ contributing</text>')
    for i, line in enumerate(desc):
        out.append(f'<text x="22" y="{72 + i*20}" font-size="13" fill="{t["fg"]}">{escape(line)}</text>')
    out.append(f'<circle cx="28" cy="{H-26}" r="6" fill="{lang["color"]}"/>'
               f'<text x="40" y="{H-21}" font-size="13" fill="{t["dim"]}">{escape(lang["name"])}</text>'
               f'<text x="{W-22}" y="{H-21}" text-anchor="end" font-size="13" fill="{t["dim"]}">★ {r["stargazerCount"]}   ⑂ {r["forkCount"]}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    if sys.argv[1] == "--mock":
        user, out_dir = mock(), sys.argv[2]
    else:
        user, out_dir = fetch(sys.argv[1], os.environ["GITHUB_TOKEN"]), sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    by_name = {r["name"]: r for r in user["repositories"]["nodes"]}
    for theme, t in THEMES.items():
        with open(os.path.join(out_dir, f"card-{theme}.svg"), "w") as f:
            f.write(card(user, t))
        for name in FEATURED:
            if name in by_name:
                with open(os.path.join(out_dir, f"repo-{name}-{theme}.svg"), "w") as f:
                    f.write(repo_card(by_name[name], t))
            else:
                print(f"warning: featured repo {name!r} not found", file=sys.stderr)


if __name__ == "__main__":
    main()
