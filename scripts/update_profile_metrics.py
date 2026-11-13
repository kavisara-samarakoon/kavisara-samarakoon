#!/usr/bin/env python3
"""Generate compact GitHub profile SVGs from public GitHub API data.

Only public repositories are counted. Commits include authored commits on
the default branches of the user's public repositories since January 1 UTC.
Language percentages are based on GitHub's reported repository language bytes.
Run by .github/workflows/profile-metrics.yml with no third-party stat service.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
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
SINCE = datetime(NOW.year, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
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
    """Render two compact rounded cards, with optional low-motion SVG accents."""
    panel_start = "#08130F" if dark else "#FBFDFB"
    panel_end = "#102019" if dark else "#F0F8F3"
    border = "#345D47" if dark else "#BEDCC8"
    fg = "#F1FAF4" if dark else "#172A20"
    muted = "#AAC1B1" if dark else "#4A6857"
    green = "#C9FF2E" if dark else "#457C0B"
    cyan = "#60DFD0" if dark else "#178979"
    barbg = "#293D32" if dark else "#DDEADF"
    palette = ["#A9ED3E", "#54CEBF", "#84A8EB"] if dark else [
        "#78AC22", "#219E91", "#597FC6"
    ]

    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1100 190" role="img" aria-labelledby="title desc">',
        '<title id="title">Public GitHub activity and languages</title>',
        '<desc id="desc">Calendar-year authored commits on public repository '
        'default branches, public repository count, stars, and leading '
        'languages by code bytes. Refreshed daily.</desc>',
        '<defs>',
        f'<linearGradient id="panel" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{panel_start}"/>'
        f'<stop offset="100%" stop-color="{panel_end}"/>'
        '</linearGradient>',
        f'<linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">'
        f'<stop offset="0%" stop-color="{green}" stop-opacity=".08"/>'
        f'<stop offset="48%" stop-color="{green}" stop-opacity=".8"/>'
        f'<stop offset="70%" stop-color="{cyan}" stop-opacity=".75"/>'
        f'<stop offset="100%" stop-color="{cyan}" stop-opacity=".08"/>'
        '</linearGradient>',
        '<clipPath id="languageBar">'
        '<rect x="582" y="73" width="468" height="12" rx="6"/>'
        '</clipPath>',
        '<clipPath id="cardOne"><rect x="12" y="12" width="524" '
        'height="168" rx="19"/></clipPath>',
        '<clipPath id="cardTwo"><rect x="551" y="12" width="537" '
        'height="168" rx="19"/></clipPath>',
        # Media-query avoids perpetual animation for users who prefer less motion.
        '<style>',
        '@keyframes flow { from { stroke-dashoffset: 530; }'
        ' to { stroke-dashoffset: 0; } }',
        '@keyframes shimmer { from { transform: translateX(0px); }'
        ' to { transform: translateX(590px); } }',
        '@keyframes breathe { 0%,100% { opacity: .35; }'
        ' 50% { opacity: .95; } }',
        '@media (prefers-reduced-motion: no-preference) {',
        '.signal { animation: flow 11s linear infinite; }',
        '.signal.delay { animation-duration: 14s; animation-delay: -5s; }',
        '.shimmer { animation: shimmer 7s ease-in-out infinite; }',
        '.node { animation: breathe 4.5s ease-in-out infinite; }',
        '}',
        '</style>',
        '</defs>',
        '<rect x="12" y="12" width="524" height="168" rx="19" '
        f'fill="url(#panel)" stroke="{border}" stroke-width="1.4"/>',
        '<rect x="551" y="12" width="537" height="168" rx="19" '
        f'fill="url(#panel)" stroke="{border}" stroke-width="1.4"/>',
        # Short accent rails distinguish the two cards without a heavy heading.
        '<path d="M37 35H511 M579 35H1059" '
        'stroke="url(#accent)" stroke-width="1.8" fill="none"/>',
        f'<path class="signal" d="M37 35H511" stroke="{green}" '
        'stroke-opacity=".45" stroke-width="2.2" fill="none" '
        'stroke-dasharray="18 512" stroke-linecap="round"/>',
        f'<path class="signal delay" d="M579 35H1059" stroke="{cyan}" '
        'stroke-opacity=".43" stroke-width="2.2" fill="none" '
        'stroke-dasharray="18 512" stroke-linecap="round"/>',
        f'<circle class="node" cx="505" cy="35" r="3" fill="{green}"/>',
        f'<circle class="node" cx="1054" cy="35" r="3" fill="{cyan}"/>',
        f'<text x="38" y="56" fill="{green}" font-family="Arial,sans-serif" '
        'font-size="14" font-weight="700" letter-spacing="1.5">'
        'PUBLIC ACTIVITY</text>',
        f'<text x="581" y="56" fill="{green}" font-family="Arial,sans-serif" '
        'font-size="14" font-weight="700" letter-spacing="1.5">'
        'LANGUAGES BY CODE BYTES</text>',
    ]
    year_label = str(NOW.year)
    for x, value, label in (
        (38, commits, f"COMMITS · {year_label}"),
        (220, repo_count, "PUBLIC REPOS"),
        (393, stars, "REPO STARS"),
    ):
        elements.extend([
            f'<text x="{x}" y="118" fill="{fg}" font-family="Arial,sans-serif" '
            f'font-size="41" font-weight="700">{value:,}</text>',
            f'<text x="{x}" y="144" fill="{muted}" font-family="Arial,sans-serif" '
            f'font-size="12.5" font-weight="700">{escape(label)}</text>',
        ])
    stamp = NOW.strftime("%d %b %Y UTC").upper()
    elements.append(
        f'<text x="38" y="166" fill="{muted}" font-family="Arial,sans-serif" '
        f'font-size="11.5">Updated {escape(stamp)}</text>'
    )
    elements.append(
        f'<rect x="582" y="73" width="468" height="12" rx="6" fill="{barbg}"/>'
    )
    offset = 582.0
    for i, (_, percent) in enumerate(langs[:3]):
        width = max(0.0, 468 * percent / 100)
        elements.append(
            f'<rect clip-path="url(#languageBar)" x="{offset:.2f}" y="73" '
            f'width="{width:.2f}" height="12" fill="{palette[i]}"/>'
        )
        offset += width
    # Low-opacity bar glint: clipped to the bar, never covers the labels.
    elements.append(
        '<rect class="shimmer" clip-path="url(#languageBar)" x="520" y="73" '
        'width="50" height="12" fill="#FFFFFF" opacity=".11"/>'
    )
    for i, (name, percent) in enumerate(langs[:3]):
        x = 582 + (i % 2) * 237
        y = 121 + (i // 2) * 34
        label = name if len(name) <= 16 else name[:15] + "…"
        elements.extend([
            f'<circle cx="{x+5}" cy="{y-5}" r="4" fill="{palette[i]}"/>',
            f'<text x="{x+19}" y="{y}" fill="{fg}" '
            f'font-family="Arial,sans-serif" font-size="16.5">'
            f'{escape(label)} {percent:.1f}%</text>',
        ])
    if not langs:
        elements.append(
            f'<text x="582" y="121" fill="{muted}" '
            'font-family="Arial,sans-serif" font-size="17">'
            'No language data reported</text>'
        )
    elements.extend([
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
        f"stars={stars}, {NOW.year} default-branch commits={commits}, "
        f"languages={langs}"
    )


if __name__ == "__main__":
    main()
