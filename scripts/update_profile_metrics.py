#!/usr/bin/env python3
"""Generate compact GitHub profile SVGs from public GitHub API data.

Only public repositories are counted. Commits include authored commits on
the default branches of the user's public repositories over the past 90 days.
Language percentages are based on GitHub's reported repository language bytes.
Run by .github/workflows/profile-metrics.yml with no third-party stat service.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OWNER = "kavisara-samarakoon"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "banner"
NOW = datetime.now(timezone.utc)
SINCE = (NOW - timedelta(days=90)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
TOKEN = os.environ.get("GH_TOKEN", "")


def fetch(endpoint: str, *, empty_repo_ok: bool = False):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kavisara-profile-metrics",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request("https://api.github.com" + endpoint, headers=headers)
    try:
        with urlopen(request, timeout=25) as response:
            import json
            return json.load(response)
    except HTTPError as error:
        if error.code == 409 and empty_repo_ok:
            return []
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code} for {endpoint.split('?')[0]}"
        ) from error


def get_public_repositories() -> list[dict]:
    repos = []
    for page in range(1, 21):
        params = urlencode({"type": "owner", "per_page": 100, "page": page})
        result = fetch(f"/users/{OWNER}/repos?{params}")
        if not isinstance(result, list):
            raise RuntimeError("Unexpected public repository response")
        repos.extend(
            item for item in result
            if not item.get("private", False)
            and item.get("owner", {}).get("login", "").lower() == OWNER.lower()
        )
        if len(result) < 100:
            return repos
    raise RuntimeError("Repository pagination limit reached; refusing partial totals")


def count_authored_commits(repo_name: str) -> int:
    total = 0
    for page in range(1, 31):
        params = urlencode({
            "author": OWNER, "since": SINCE, "per_page": 100, "page": page,
        })
        result = fetch(
            f"/repos/{OWNER}/{repo_name}/commits?{params}",
            empty_repo_ok=True,
        )
        if not isinstance(result, list):
            raise RuntimeError(f"Unexpected commit response for {repo_name}")
        total += len(result)
        if len(result) < 100:
            return total
    raise RuntimeError(f"Commit pagination limit reached for {repo_name}")


def get_metrics() -> tuple[int, int, int, list[tuple[str, float]]]:
    repos = get_public_repositories()
    if not repos:
        raise RuntimeError("No public repositories returned; keeping last good image")

    total_stars = sum(int(repo.get("stargazers_count", 0)) for repo in repos)
    total_commits = 0
    languages: Counter[str] = Counter()

    for repo in repos:
        name = repo["name"]
        total_commits += count_authored_commits(name)
        result = fetch(f"/repos/{OWNER}/{name}/languages")
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected language response for {name}")
        languages.update({str(k): int(v) for k, v in result.items()})

    grand_total = sum(languages.values())
    language_mix = [
        (name, 100 * count / grand_total)
        for name, count in languages.most_common(3)
    ] if grand_total else []
    return (len(repos), total_stars, total_commits, language_mix)


def build_svg(
    repo_count: int,
    stars: int,
    commits: int,
    langs: list[tuple[str, float]],
    *,
    dark: bool,
) -> str:
    panel = "#111A16" if dark else "#F5F9F6"
    border = "#334E3C" if dark else "#C7DCCD"
    fg = "#F0F8F1" if dark else "#15251A"
    muted = "#A5B9AC" if dark else "#476253"
    green = "#C9FF2E" if dark else "#457B0A"
    cyan = "#65FFDA" if dark else "#0F887B"
    barbg = "#314238" if dark else "#D9E7DD"
    palette = ["#B4EF37", "#56CDB8", "#83A8E2"]

    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1100 194" role="img" aria-labelledby="title desc">',
        '<title id="title">GitHub public development metrics</title>',
        '<desc id="desc">Daily-updated public repository data: commits authored '
        'on default branches in the last 90 days, total stars and most used '
        'languages by code bytes.</desc>',
        '<defs><clipPath id="barClip">'
        '<rect x="580" y="72" width="462" height="12" rx="6"/>'
        '</clipPath></defs>',
        f'<rect x="12" y="13" width="524" height="169" rx="18" '
        f'fill="{panel}" stroke="{border}" stroke-width="1.4"/>',
        f'<rect x="552" y="13" width="536" height="169" rx="18" '
        f'fill="{panel}" stroke="{border}" stroke-width="1.4"/>',
        f'<text x="38" y="46" fill="{green}" font-family="Arial,sans-serif" '
        f'font-size="14" font-weight="700" letter-spacing="1.5">'
        'PUBLIC ACTIVITY</text>',
        f'<text x="578" y="46" fill="{green}" font-family="Arial,sans-serif" '
        f'font-size="14" font-weight="700" letter-spacing="1.5">'
        'LANGUAGES BY CODE BYTES</text>',
    ]
    counts = [
        (39, commits, "COMMITS · 90 DAYS"),
        (220, repo_count, "PUBLIC REPOS"),
        (394, stars, "REPO STARS"),
    ]
    for x, value, label in counts:
        elements.extend([
            f'<text x="{x}" y="111" fill="{fg}" '
            f'font-family="Arial,sans-serif" font-size="40" '
            f'font-weight="700">{value:,}</text>',
            f'<text x="{x}" y="141" fill="{muted}" '
            f'font-family="Arial,sans-serif" font-size="12.5" '
            f'font-weight="600">{label}</text>',
        ])
    stamp = NOW.strftime("%d %b %Y UTC").upper()
    elements.append(
        f'<text x="39" y="165" fill="{muted}" font-family="Arial,sans-serif" '
        f'font-size="11.5">Updated {escape(stamp)}</text>'
    )

    elements.append(
        f'<rect x="580" y="72" width="462" height="12" rx="6" fill="{barbg}"/>'
    )
    offset = 580.0
    for i, (lang, percent) in enumerate(langs):
        width = max(0.0, 462 * percent / 100)
        elements.append(
            f'<rect clip-path="url(#barClip)" x="{offset:.2f}" y="72" '
            f'width="{width:.2f}" height="12" fill="{palette[i]}"/>'
        )
        offset += width

    for i, (name, percent) in enumerate(langs):
        col = i % 2
        row = i // 2
        x = 580 + col * 235
        y = 118 + row * 34
        label = name if len(name) <= 17 else name[:16] + "…"
        elements.extend([
            f'<circle cx="{x+5}" cy="{y-5}" r="4" fill="{palette[i]}"/>',
            f'<text x="{x+18}" y="{y}" fill="{fg}" '
            f'font-family="Arial,sans-serif" font-size="17">'
            f'{escape(label)} {percent:.1f}%</text>',
        ])
    if not langs:
        elements.append(
            f'<text x="580" y="121" fill="{muted}" '
            f'font-family="Arial,sans-serif" font-size="17">'
            'No language data reported</text>'
        )
    elements.extend([
        f'<text x="580" y="165" fill="{muted}" '
        f'font-family="Arial,sans-serif" font-size="11.5">'
        'Public repositories only · remaining languages in grey</text>',
        '</svg>',
    ])
    return "\n".join(elements) + "\n"


def main() -> None:
    repo_count, stars, commits, langs = get_metrics()
    DEST.mkdir(parents=True, exist_ok=True)
    for name, dark in (
        ("github-live-metrics-dark.svg", True),
        ("github-live-metrics-light.svg", False),
    ):
        content = build_svg(repo_count, stars, commits, langs, dark=dark)
        (DEST / name).write_text(content, encoding="utf-8")
    print(
        f"Generated public metrics: repos={repo_count}, "
        f"stars={stars}, 90d default-branch commits={commits}, "
        f"languages={langs}"
    )


if __name__ == "__main__":
    main()
