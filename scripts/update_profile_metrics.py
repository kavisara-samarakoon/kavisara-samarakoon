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
    """Generate slim, animated rounded metrics with a reduced-motion fallback.

    Repository counts, stars and languages are fetched from GitHub.
    The 1000+ figure is an owner-selected static display, not an API value.
    """
    panel_a = "#071610" if dark else "#F8FCF9"
    panel_b = "#0C2018" if dark else "#EDF7EF"
    fg = "#F2FBF5" if dark else "#14281C"
    muted = "#A8BFB0" if dark else "#516B58"
    edge = "#365E48" if dark else "#B6D4BE"
    lime = "#C9FF2E" if dark else "#548A10"
    cyan = "#5AE5D4" if dark else "#168779"
    track = "#253E31" if dark else "#D9E8DD"
    lang_colors = (
        ["#B3F34D", "#5CD4C1", "#8FB2EE"] if dark
        else ["#6BA52B", "#199989", "#5A82CD"]
    )

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 1100 152" role="img" aria-labelledby="title desc">',
        '<title id="title">Public GitHub activity and programming languages</title>',
        '<desc id="desc">Verified public data: authored commits on public '
        'repository default branches during the current calendar year, '
        'public repository count, stars, and languages by code bytes. '
        'The 1000+ featured commits figure is a manually selected display, not an API measurement.</desc>',
        '<defs>',
        f'<linearGradient id="panel" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{panel_a}"/>'
        f'<stop offset="100%" stop-color="{panel_b}"/>'
        '</linearGradient>',
        f'<linearGradient id="frame" x1="0%" y1="0%" x2="100%" y2="0%">'
        f'<stop offset="0%" stop-color="{lime}" stop-opacity=".12"/>'
        f'<stop offset="45%" stop-color="{lime}" stop-opacity=".75"/>'
        f'<stop offset="68%" stop-color="{cyan}" stop-opacity=".65"/>'
        f'<stop offset="100%" stop-color="{cyan}" stop-opacity=".12"/>'
        '</linearGradient>',
        '<clipPath id="barClip">'
        '<rect x="581" y="64" width="473" height="10" rx="5"/>'
        '</clipPath>',
        '<style>',
        '@keyframes borderFlow {from {stroke-dashoffset: 1320;} '
        'to {stroke-dashoffset: 0;}}',
        '@keyframes scan {from {transform:translateX(-70px);}'
        ' to {transform:translateX(560px);}}',
        '@keyframes softPulse {0%,100% {opacity:.4;} 50% {opacity:.85;}}',
        '@media (prefers-reduced-motion: no-preference) {',
        '.framePulse {animation:borderFlow 16s linear infinite;}',
        '.framePulse.reverse {animation-duration:19s;animation-direction:reverse;}',
        '.scan {animation:scan 8s linear infinite;}',
        '.signalDot {animation:softPulse 5s ease-in-out infinite;}',
        '}',
        '</style>',
        '</defs>',
        # Transparent outside two cards. No full-width background rectangle.
        f'<rect x="12" y="10" width="524" height="132" rx="17" '
        f'fill="url(#panel)" stroke="{edge}" stroke-width="1.4"/>',
        f'<rect x="552" y="10" width="536" height="132" rx="17" '
        f'fill="url(#panel)" stroke="{edge}" stroke-width="1.4"/>',
        # Animated moving glints follow rounded borders. Static borders remain.
        f'<rect class="framePulse" x="13" y="11" width="522" height="130" '
        f'rx="16" fill="none" stroke="{lime}" stroke-opacity=".65" '
        'stroke-width="2" stroke-dasharray="54 1320"/>',
        f'<rect class="framePulse reverse" x="553" y="11" '
        'width="534" height="130" rx="16" fill="none" '
        f'stroke="{cyan}" stroke-opacity=".6" stroke-width="2" '
        'stroke-dasharray="54 1320"/>',
        f'<circle class="signalDot" cx="508" cy="28" r="2.5" '
        f'fill="{lime}"/>',
        f'<circle class="signalDot" cx="1059" cy="28" r="2.5" '
        f'fill="{cyan}"/>',
        f'<text x="37" y="39" fill="{lime}" font-family="Arial,sans-serif" '
        'font-size="12.8" font-weight="700" letter-spacing="1.3">'
        'PUBLIC ACTIVITY</text>',
        f'<text x="580" y="39" fill="{lime}" font-family="Arial,sans-serif" '
        'font-size="12.8" font-weight="700" letter-spacing="1.3">'
        'LANGUAGES BY CODE BYTES</text>',
    ]

    for x, value, label in (
        (37, "1000+", f"COMMITS · {NOW.year}"),
        (223, repo_count, "PUBLIC REPOS"),
        (399, stars, "REPO STARS"),
    ):
        display = value if isinstance(value, str) else f"{value:,}"
        lines.extend([
            f'<text x="{x}" y="90" fill="{fg}" font-family="Arial,sans-serif" '
            f'font-size="38" font-weight="700">{display}</text>',
            f'<text x="{x}" y="111" fill="{muted}" font-family="Arial,sans-serif" '
            f'font-size="12.5" font-weight="700">{escape(label)}</text>',
        ])
    lines.append(
        f'<rect x="581" y="64" width="473" height="10" rx="5" '
        f'fill="{track}"/>'
    )
    offset = 581.0
    for i, (_, pct) in enumerate(langs[:3]):
        width = 473 * max(0.0, min(100.0, pct)) / 100
        lines.append(
            f'<rect clip-path="url(#barClip)" x="{offset:.2f}" y="64" '
            f'width="{width:.2f}" height="10" fill="{lang_colors[i]}"/>'
        )
        offset += width
    # A moving highlight travels only within the rounded language bar.
    lines.append(
        '<rect class="scan" clip-path="url(#barClip)" x="560" y="64" '
        'width="42" height="10" fill="#FFFFFF" opacity=".10"/>'
    )

    for i, (name, pct) in enumerate(langs[:3]):
        x = 581 + (i % 2) * 235
        y = 102 + (i // 2) * 28
        label = name if len(name) <= 16 else name[:15] + "…"
        lines.extend([
            f'<circle cx="{x+5}" cy="{y-5}" r="4" '
            f'fill="{lang_colors[i]}"/>',
            f'<text x="{x+18}" y="{y}" fill="{fg}" '
            f'font-family="Arial,sans-serif" font-size="16">'
            f'{escape(label)} {pct:.1f}%</text>',
        ])
    if not langs:
        lines.append(
            f'<text x="581" y="101" fill="{muted}" '
            'font-family="Arial,sans-serif" font-size="16">'
            'No language data reported</text>'
        )

    lines.append('</svg>')
    return "\n".join(lines) + "\n"


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
