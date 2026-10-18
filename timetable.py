import asyncio
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

DAY_RE = re.compile(
    r"(Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье)[^-–\d]*[-–]\s*(\d{2}\.\d{2}\.\d{4})"
)
TIME_RE = re.compile(r"(\d{1,2}:\d{2})\D+(\d{1,2}:\d{2})")
CHANGE_WORDS = ("Замена", "Перенос", "Внеплановый", "Отмен", "не будет")

CACHE_TTL = 300
_cache = {}


@dataclass
class Lesson:
    start: str
    end: str
    text: str
    changed: bool


def _clean(text: str) -> str:
    text = text.replace("▾", " ")
    text = re.sub(r"(Вся группа,?\s*)+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _find_day(table):
    for tag in table.find_all_previous(limit=15):
        text = tag.get_text(" ", strip=True)
        if len(text) < 60:
            match = DAY_RE.search(text)
            if match:
                return datetime.strptime(match.group(2), "%d.%m.%Y").date()
    return None


def parse_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for table in soup.find_all("table"):
        day = _find_day(table)
        if day is None:
            continue
        lessons = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            time_match = TIME_RE.search(cells[0].get_text(" ", strip=True))
            if not time_match:
                continue
            text = _clean(cells[1].get_text(" ", strip=True))
            lessons.append(
                Lesson(
                    start=time_match.group(1).zfill(5),
                    end=time_match.group(2).zfill(5),
                    text=text,
                    changed=any(w in text for w in CHANGE_WORDS),
                )
            )
        result[day] = lessons
    return result


async def get_week(url: str) -> dict:
    now = time.time()
    cached = _cache.get(url)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        data = parse_html(html)
        if not data:
            raise ValueError("На странице не найдено расписание")
        _cache[url] = (now, data)
        return data
    except Exception:
        if cached:
            return cached[1]
        raise


def url_for_date(url: str, day: date) -> str:
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    query["date"] = day.isoformat()
    return urlunparse(parts._replace(query=urlencode(query)))


async def get_week_for(url: str, day: date) -> dict:
    data = await get_week(url)
    if day in data:
        return data
    return await get_week(url_for_date(url, day))



def format_day(data: dict, day: date):
    if day not in data:
        return None
    title = f"{WEEKDAYS[day.weekday()]}, {day.strftime('%d.%m')}"
    lessons = data[day]
    if not lessons:
        return f"{title}\n\nПар нет"
    lines = [title, ""]
    for lesson in lessons:
        mark = "⚠️ " if lesson.changed else ""
        lines.append(f"{lesson.start}–{lesson.end}")
        lines.append(f"{mark}{lesson.text}")
        lines.append("")
    return "\n".join(lines).strip()


def format_week(data: dict) -> str:
    days = [d for d in sorted(data) if d.weekday() < 5 or data[d]]
    return "\n\n".join(format_day(data, d) for d in days)


def format_changes(data: dict):
    parts = []
    for day in sorted(data):
        changed = [l for l in data[day] if l.changed]
        if changed:
            parts.append(f"{WEEKDAYS[day.weekday()]}, {day.strftime('%d.%m')}")
            for l in changed:
                parts.append(f"  {l.start}–{l.end} {l.text}")
            parts.append("")
    return "\n".join(parts).strip() or None


def format_bells(data: dict):
    slots = sorted({(l.start, l.end) for lessons in data.values() for l in lessons})
    if not slots:
        return None
    return "\n".join(f"{s}–{e}" for s, e in slots)



if __name__ == "__main__":
    default_url = "https://site.mstimetables.ru/01a00f53d32773b5b396bf3eb6f57ce2/groups/309"
    page_url = sys.argv[1] if len(sys.argv) > 1 else default_url
    week = asyncio.run(get_week(page_url))
    print(format_week(week))
    print("\n--- Замены ---")
    print(format_changes(week) or "нет")
    print("\n--- Звонки ---")
    print(format_bells(week) or "нет данных")
