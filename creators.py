"""Build ideas from YouTube creators, through the public RSS feed of each channel (no API key, no scraping).

A channel's feed (https://www.youtube.com/feeds/videos.xml?channel_id=UC…) lists its latest videos with title, link
and the full description. Creators who publish builds usually put an Overframe link and/or the mod list in the
description: those are picked out here and offered as builds in the Builds tab. Nothing is read from the videos
themselves (no transcripts, no images).
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import builds as B
from config import APP_DIR, CFG

CACHE_FILE = APP_DIR / "creators_cache.json"
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id="
MAX_FEED = 1_500_000
UA = "WFVendorOverlay (creator feed; user-initiated)"
CHANNEL_ID = re.compile(r"UC[0-9A-Za-z_-]{22}")
OVERFRAME = re.compile(r"https?://(?:www\.)?overframe\.gg/build/\d+[^\s\"'<>)\]]*", re.I)
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}

# the 10 channels offered by default (public lists of Warframe channels: ID and name as published there; the name
# actually shown comes from the feed itself, so a wrong ID is noticed at once)
DEFAULT_CHANNELS = [
    ("MHBlacky", "UCWT_Apn0qHyy_f_RFYYOGdQ"), ("Tactical Potato", "UCHAenboNPQJmNQmvQDQibQA"),
    ("iFlynn", "UCjHhQ3k4zQ2Y8-CPM7KpGww"), ("KnightmareFrame", "UC9BVPiqY_Dc3hbcmDKatazA"),
    ("Grind Hard Squad", "UCTR7wxZ_91orxoOXiKr5GDw"), ("Brozime", "UCJ6-So7ndDeeYdudPIbhCiA"),
    ("LeyzarGamingViews", "UCXeubDV2dwI-V9FO9oiDu3A"), ("Sabuuchi", "UC71VEEy4Y6JVtF6GhIJ_-PQ"),
    ("TheKengineer", "UCiED7CqmvQSsSHUiQ42EWbw"), ("kyaii", "UCZy6dztKYlf3et6OcwU47EQ"),
]
DEFAULT_SETTING = ", ".join(f"{n}={i}" for n, i in DEFAULT_CHANNELS)


class CreatorError(Exception):
    pass


def parse_channels(text: str) -> list:
    """The channels setting: items separated by commas/newlines, each "UC…", a /channel/UC… link or "Name=UC…".
    Returns [(label, channel_id)] (up to 20); items without a channel ID (e.g. @handles) are skipped."""
    out, seen = [], set()
    for part in re.split(r"[,\n;]", text or ""):
        m = CHANNEL_ID.search(part)
        if not m or m.group(0) in seen:
            continue
        seen.add(m.group(0))
        label = part.split("=", 1)[0].strip() if "=" in part else ""
        out.append((label if label and not CHANNEL_ID.search(label) else "", m.group(0)))
    return out[:20]


def unresolved(text: str) -> list:
    """Items of the setting without a channel ID (YouTube @handles do not contain it)."""
    return [p.strip() for p in re.split(r"[,\n;]", text or "") if p.strip() and not CHANNEL_ID.search(p)]


def parse_feed(xml_text: str) -> dict:
    """{"channel": name, "videos": [{"id","title","url","published","desc"}]} from an Atom feed. Raises CreatorError."""
    if "<!DOCTYPE" in xml_text or "<!ENTITY" in xml_text:
        raise CreatorError("unexpected XML")                # entity tricks: never needed by a YouTube feed
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise CreatorError(f"not a valid feed ({e})")
    channel = (root.findtext("a:author/a:name", default="", namespaces=NS) or root.findtext("a:title", default="",
                                                                                         namespaces=NS)).strip()
    videos = []
    for e in root.findall("a:entry", NS):
        vid = (e.findtext("yt:videoId", default="", namespaces=NS) or "").strip()
        if not vid:
            continue
        link = e.find("a:link[@rel='alternate']", NS)
        videos.append({
            "id": vid, "title": (e.findtext("a:title", default="", namespaces=NS) or "").strip(),
            "url": link.get("href") if link is not None else "https://www.youtube.com/watch?v=" + vid,
            "published": (e.findtext("a:published", default="", namespaces=NS) or "")[:10],
            "desc": (e.findtext("m:group/m:description", default="", namespaces=NS) or "").strip()})
    return {"channel": channel, "videos": videos}


def fetch_feed(channel_id: str, timeout: float = 15.0) -> dict:
    if not CHANNEL_ID.fullmatch(channel_id):
        raise CreatorError("not a channel ID")
    req = urllib.request.Request(FEED_URL + urllib.parse.quote(channel_id), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_FEED + 1)
    except urllib.error.HTTPError as e:
        raise CreatorError(f"HTTP {e.code} (wrong channel ID?)")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise CreatorError(f"{type(e).__name__}: {e}")
    if len(raw) > MAX_FEED:
        raise CreatorError("feed too large")
    return parse_feed(raw.decode("utf-8", errors="replace"))


BUILD_WORDS = re.compile(r"\b(builds?|loadouts?|set-?ups?|guide|best (?:mods?|build)|mod ?(?:config|setup|list)|"
                         r"how to (?:build|mod)|steel path|incarnon|endurance|eximus|riven)\b", re.I)
OFF_TOPIC = re.compile(r"\b(news|devstream|dev ?stream|prime access|trailer|patch ?notes?|hotfix|update \d|"
                       r"podcast|reaction|react(?:s|ing)? to|q&a|tennogen|fashion ?frame|lore|story|"
                       r"highlights?|funny|fails?|memes?|montage|livestream|giveaway|unboxing|review|"
                       r"tier ?list|tennocon|prime resurgence|baro|void trader|relics? (?:opening|run)|"
                       r"#shorts?)\b", re.I)
LIST_BULLET = re.compile(r"^[\s\-\u2013\u2022*\u00b7>\d.):\[\]]*(?:\d{1,2}:\d{2}(?::\d{2})?\s*[-\u2013]?\s*)?")


def listed_mods(desc: str, market) -> list:
    """Mod names that sit on lines looking like a mod list ("- Serration", "Blind Rage (r10)", "Flow, Rush, Vigor"),
    not names that merely occur in a sentence ("Flow of the game"). In order of appearance, without repeats."""
    out, seen = [], set()
    for line in OVERFRAME.sub(" ", desc or "").splitlines():
        line = LIST_BULLET.sub("", line).strip()
        if not line or len(line) > 90:
            continue
        found = B.extract_mods(line, market)
        if not found:
            continue
        rest = line
        for _s, name in found:
            rest = rest.replace(name, " ")
        rest = re.sub(r"\(.*?\)|\b(?:rank|r|x)\s*\d+\b|[-\u2013:,;/+&|]", " ", rest, flags=re.I)
        if len(rest.split()) <= 3:                  # little besides the names: it is a list line
            for slug, name in found:
                if slug not in seen:
                    seen.add(slug)
                    out.append((slug, name))
    return out


def relevance(title: str, links: list, listed: int, desc: str) -> int:
    """How likely a video is a Warframe build video (0 = not at all). Overframe link +3, build words in the title +2,
    a mod list in the description +1 (4+ mods) / +2 (8+ mods), off-topic words in the title -4, no mention of Warframe (and a short mod list) -2."""
    score = 0
    if links:
        score += 3
    if BUILD_WORDS.search(title or ""):
        score += 2
    if listed >= 8:
        score += 2
    elif listed >= 4:
        score += 1
    if OFF_TOPIC.search(title or ""):
        score -= 4
    if "warframe" not in f"{title} {desc}".lower() and not links and listed < 8:
        score -= 2
    return score


def analyse(video: dict, market) -> dict:
    """Adds what the description holds: Overframe links, the mods listed in it and a relevance score."""
    desc = video.get("desc", "")
    links = list(dict.fromkeys(m.group(0).rstrip(".,;") for m in OVERFRAME.finditer(desc)))
    mods = listed_mods(desc, market) if market is not None else []
    return dict(video, links=links, mods=mods, score=relevance(video.get("title", ""), links, len(mods), desc))


def min_score() -> int:
    try:
        return max(1, int(CFG["creator_min_relevance"]))
    except (KeyError, TypeError, ValueError):
        return 3


def collect(market, channels, per_channel=10, fetch=fetch_feed):
    """Reads the feeds. Returns (videos, errors): only videos that look like build videos (relevance >= the setting,
    and an Overframe link or a list of at least 4 mods), best first within each day; errors = [(label, message)]."""
    videos, errors = [], []
    need = min_score()
    for label, cid in channels:
        try:
            feed = fetch(cid)
        except CreatorError as e:
            errors.append((label or cid, str(e)))
            continue
        for v in feed["videos"][:per_channel]:
            a = analyse(v, market)
            if a["score"] >= need and (a["links"] or len(a["mods"]) >= 4):
                videos.append({"channel": feed["channel"] or label or cid, "cid": cid, "id": a["id"],
                               "title": a["title"], "url": a["url"], "published": a["published"],
                               "links": a["links"], "mods": [[s, n] for s, n in a["mods"]], "score": a["score"]})
    videos.sort(key=lambda v: (v["published"], v["score"]), reverse=True)
    return videos, errors


def load_cache() -> dict:
    try:
        d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_cache(videos, errors):
    try:
        CACHE_FILE.write_text(json.dumps({"time": int(time.time()), "videos": videos, "errors": errors},
                                         ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
