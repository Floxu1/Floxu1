"""Render daily profile images from GitHub's public repository and contribution data."""

from collections import Counter
from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw


USER = "Floxu1"
API = "https://api.github.com"
FEATURED = {
    "android": "UAC-SNI-Spoofer-Android",
    "windows": "UAC-SNI-Spoofer-Windows",
    "gateway": "UAC-GATEWAY",
    "android-tv": "BehroozuacV2ray-Android-TV",
}
DARK = ("#081321", "#182a3b", "#20596b", "#247e92", "#35adbc", "#73f0e6", "#effeff")
LIGHT = ("#f0f7fa", "#d8e7ee", "#b4d8e2", "#74b9ce", "#3087a2", "#19617e", "#132b45")


def fetch(url):
    headers = {"User-Agent": "Floxu1-profile-assets", "Accept-Language": "en-US"}
    token = os.environ.get("GITHUB_TOKEN")
    if url.startswith(API + "/") and token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read().decode()


class PublicCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.tooltip = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs and "data-level" in attrs:
            self.cells[attrs["id"]] = (date.fromisoformat(attrs["data-date"]), int(attrs["data-level"]))
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day-component-"):
            self.tooltip = attrs["for"]

    def handle_data(self, text):
        if self.tooltip and (match := re.search(r"(No|[\d,]+) contributions? on ", text)):
            value = match[1].replace(",", "")
            self.counts[self.tooltip] = 0 if value == "No" else int(value)

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.tooltip = None


def contribution_days():
    # Match the calendar a signed-out GitHub visitor sees.
    calendar = PublicCalendar()
    calendar.feed(fetch(f"https://github.com/users/{USER}/contributions"))
    return {day: (calendar.counts[cell], level) for cell, (day, level) in calendar.cells.items()}


def public_repositories():
    repos = []
    page = 1
    while True:
        batch = json.loads(fetch(f"{API}/users/{USER}/repos?type=owner&per_page=100&page={page}"))
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def language_share(repos):
    totals = Counter()
    for repo in repos:
        if not repo["fork"] and repo["language"]:
            totals.update(json.loads(fetch(repo["languages_url"])))
    if not totals:
        return []
    total = totals.total()
    top = totals.most_common(3)
    other = total - sum(count for _, count in top)
    return [(name, count / total) for name, count in top + ([('Other', other)] if other else [])]


def svg_text(x, y, value, size=22, color="#bdd3e4", weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(str(value))}</text>')


def svg(width, height, title, layers):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" font-family="system-ui, Segoe UI, sans-serif">\n'
            f'<title>{escape(title)}</title>\n' + '\n'.join(layers) + '\n</svg>\n')


def weekly_counts(days):
    first, last = min(days), max(days)
    while (first.weekday() + 1) % 7:
        first -= timedelta(days=1)
    weeks = [[days.get(first + timedelta(days=offset + row)) for row in range(7)]
             for offset in range(0, (last - first).days + 1, 7)]
    return weeks, first


def render_stats(path, repos, followers, languages, days, weeks, first_week):
    stars = sum(repo["stargazers_count"] for repo in repos)
    total = sum(count for count, _ in days.values())
    layers = [
        '<rect x=".5" y=".5" width="719" height="331" rx="14" fill="#081321" stroke="#28445b"/>',
        '<path d="M26 107H694 M26 244H694" fill="none" stroke="#243e53"/>',
    ]
    for x, number, name in ((28, stars, "Repository stars"), (276, followers, "Followers"), (507, len(repos), "Public repos")):
        layers.extend((svg_text(x, 57, f"{number:,}", 39, "#e8f7ff", 700), svg_text(x, 86, name)))
    layers.append(svg_text(28, 140, "Weekly contributions", 24, "#e8f7ff", 650))
    layers.append(svg_text(692, 140, f"{total:,} in the last year", 22, "#73f0e6", 600, "end"))
    sums = [sum(day[0] for day in week if day is not None) for week in weeks]
    max_week = max(1, *sums)
    stride = 664 / len(weeks)
    for index, count in enumerate(sums):
        x = 28 + index * stride
        height = 3 + 47 * count / max_week
        color = DARK[1] if count == 0 else DARK[3 + (count > max_week * 0.22) + (count > max_week * 0.6)]
        layers.append(f'<rect x="{x:.2f}" y="{209 - height:.2f}" width="{stride - 3:.2f}" height="{height:.2f}" rx="1.5" fill="{color}"/>')
    for index in range(0, len(weeks), 10):
        month = (first_week + timedelta(weeks=index)).strftime("%b")
        layers.append(svg_text(round(28 + index * stride), 230, month, 17))

    layers.append(svg_text(28, 274, "Languages by bytes", 21, "#e8f7ff", 600))
    layers.append(svg_text(692, 274, max(days).isoformat(), 18, "#a0b6cc", 400, "end"))
    x = 28
    colors = ("#73f0e6", "#84a7ff", "#a6bdf1", "#a0b6cc")
    for (name, fraction), color in zip(languages, colors):
        width = fraction * 664
        layers.append(f'<rect x="{x:.2f}" y="284" width="{width:.2f}" height="5" fill="{color}"/>')
        x += width
    for index, ((name, fraction), color) in enumerate(zip(languages, colors)):
        layers.append(svg_text(28 + index * 166, 316, f"{name} {fraction:.0%}", 20, color))
    title = f"{stars:,} stars, {followers:,} followers, {len(repos)} public repos and {total:,} contributions in the last year"
    path.write_text(svg(720, 332, title, layers), encoding="utf-8")


def render_snake(folder, weeks, theme, colors):
    stride = 13
    size = (len(weeks) * stride + 23, 114)
    board = Image.new("RGB", size, colors[0])
    draw = ImageDraw.Draw(board)

    def bounds(column, row, radius=5):
        x, y = 17 + column * stride, 18 + row * stride
        return x - radius, y - radius, x + radius, y + radius

    path = []
    for column, week in enumerate(weeks):
        for row in (range(7) if column % 2 == 0 else range(6, -1, -1)):
            if week[row] is not None:
                _, level = week[row]
                draw.rounded_rectangle(bounds(column, row), radius=2, fill=colors[1 + level])
            path.append((column, row))
    board.save(folder / f"snake-{theme}.png", optimize=True)
    initial_board = board.copy()

    palette = board.quantize()
    palette.putpalette([int(color[index:index + 2], 16) for color in colors for index in (1, 3, 5)])
    frames = [board.quantize(palette=palette, dither=Image.Dither.NONE)]
    for index, (column, row) in enumerate(path):
        if weeks[column][row] is not None:
            draw.rounded_rectangle(bounds(column, row), radius=2, fill=colors[1])
        frame = board.copy()
        trace = ImageDraw.Draw(frame)
        body = path[max(0, index - 10):index + 1]
        points = [bounds(x, y, 0)[:2] for x, y in body]
        trace.line(points, fill=colors[3], width=4)
        trace.line(points[-6:], fill=colors[5], width=4)
        trace.rounded_rectangle(bounds(column, row, 4), radius=2, fill=colors[6])
        frames.append(frame.quantize(palette=palette, dither=Image.Dither.NONE))

    # Restore the contribution map in a sweep before the snake loops.
    for step in range(16, -1, -1):
        edge = size[0] * step // 17
        restored = frame.copy()
        restored.paste(initial_board.crop((edge, 0, *size)), (edge, 0))
        frames.append(restored.quantize(palette=palette, dither=Image.Dither.NONE))
    gif = folder / f"snake-{theme}.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], loop=0, optimize=True,
                   duration=[440] + [40] * (len(path) - 1) + [260] + [40] * 17)
    with Image.open(gif) as output:
        assert output.n_frames >= len(path) and output.info["loop"] == 0, gif


def render(output):
    profile = json.loads(fetch(f"{API}/users/{USER}"))
    repos = public_repositories()
    days = contribution_days()
    if not 360 <= len(days) <= 373 or not all(0 <= level <= 4 and count >= 0 for count, level in days.values()):
        raise ValueError("GitHub returned an incomplete contribution calendar")
    weeks, first = weekly_counts(days)
    assert sum(day is not None for week in weeks for day in week) == len(days)
    output.mkdir(exist_ok=True, parents=True)
    render_stats(output / "stats.svg", repos, profile["followers"], language_share(repos), days, weeks, first)
    for slug, name in FEATURED.items():
        stars = next(repo["stargazers_count"] for repo in repos if repo["name"] == name)
        layers = [
            '<rect x=".5" y=".5" width="71" height="25" rx="7" fill="#102234" stroke="#38576d"/>',
            '<path d="m14 6 1.9 3.8 4.2.6-3.1 3 .7 4.2-3.7-2-3.7 2 .7-4.2-3.1-3 4.2-.6Z" fill="none" stroke="#73f0e6" stroke-linejoin="round"/>',
            svg_text(29, 18, f"{stars:,}", 14, "#e8f7ff", 650),
        ]
        (output / f"stars-{slug}.svg").write_text(svg(72, 26, f"{name}: {stars:,} stargazers", layers), encoding="utf-8")
    for theme, colors in (("dark", DARK), ("light", LIGHT)):
        render_snake(output, weeks, theme, colors)
    print(f"Rendered {len(repos)} public repositories and {len(days)} dates through {max(days)}.")


if __name__ == "__main__":
    render(Path(sys.argv[1]))
