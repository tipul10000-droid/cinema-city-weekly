"""Weekly Cinema City (Israel) scan: now-showing movies + IMDb + Rotten Tomatoes.

Writes docs/data.json (for the GitHub Pages site) and sends one ntfy.sh push.
Stdlib only, so the GitHub Action needs no pip install.
"""
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SITE = "https://www.cinema-city.co.il"
WIX_CODE_APP = "675bbcef-18d8-41f5-800e-131ec9e08762"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
IL = ZoneInfo("Asia/Jerusalem")
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "docs", "data.json")
PAGE_URL = os.environ.get("PAGE_URL", "https://tipul10000-droid.github.io/cinema-city-weekly/")

# Hebrew version suffixes on Cinema City titles ("-מדובב", "-אנגלית", ...)
VERSION_RE = re.compile(r"\s*-\s*(מדובב.*|אנגלית|מתורגם.*|Infinity Vi.*)$")
FOREIGN_DUB_RE = re.compile(r"(לרוסית|לצרפתית)")


def http(url, data=None, headers=None, timeout=30, tries=1, wait=5):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    h.update(headers or {})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception:
            if i == tries - 1:
                print("request failed:", url.split("?")[0])
                raise
            time.sleep(wait * (i + 1) ** 2)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9֐-׿]+", "", s)


# ---------- Cinema City ----------

def fetch_cinema_city():
    tokens = json.loads(http(f"{SITE}/_api/v1/access-tokens", tries=4, wait=30))
    inst = tokens["apps"][WIX_CODE_APP]["instance"]
    items, offset = [], 0
    while True:
        body = json.dumps({"dataCollectionId": "SyncFeatures",
                           "query": {"paging": {"limit": 100, "offset": offset}},
                           "returnTotalCount": True}).encode()
        res = json.loads(http(f"{SITE}/_api/cloud-data/v2/items/query", data=body, tries=4, wait=30,
                              headers={"Authorization": inst,
                                       "Content-Type": "application/json"}))
        items += [d["data"] for d in res.get("dataItems", [])]
        total = res.get("pagingMetadata", {}).get("total", 0)
        offset += 100
        if offset >= total:
            return items


def now_showing(items, now):
    horizon = now + timedelta(days=7)
    movies = {}
    for it in items:
        p = it.get("payloadJson") or {}
        en = (p.get("additionalName") or "").strip()
        he = (it.get("name") or "").strip()
        nxt = (it.get("closestPresentationDateTime") or {}).get("$date")
        if p.get("featureTypeId") != 1 or not en or not nxt:
            continue  # events/shows, or nothing scheduled
        if FOREIGN_DUB_RE.search(he):
            continue  # Russian/French dubs duplicate the main entry
        nxt_dt = datetime.fromisoformat(nxt.replace("Z", "+00:00"))
        started = p.get("dateStarted")
        if nxt_dt > horizon or (started and datetime.fromisoformat(started).replace(tzinfo=IL) > horizon):
            continue  # pre-sale for a far-away premiere
        version = (VERSION_RE.search(he).group(1) if VERSION_RE.search(he) else "")
        he_clean = VERSION_RE.sub("", he).strip()
        key = norm(en)
        m = movies.setdefault(key, {
            "title": en, "title_he": he_clean, "cc_id": it.get("externalId"),
            "cc_url": f"{SITE}/movie/{it.get('externalId')}",
            "poster": it.get("image"), "genre": ", ".join(it.get("genre") or []),
            "duration": it.get("duration"), "rating_age": it.get("ratingName"),
            "language": p.get("originalLanguageISO"), "date_started": started,
            "versions": [], "next_show": nxt, "has_original": False,
        })
        if not version.startswith("מדובב"):
            m["has_original"] = True
        if version and version not in m["versions"]:
            m["versions"].append(version)
        if nxt < m["next_show"]:
            m["next_show"] = nxt
        if not version:  # link to the original-language entry when there is one
            m["cc_id"], m["cc_url"] = it.get("externalId"), f"{SITE}/movie/{it.get('externalId')}"
    return list(movies.values())


# ---------- IMDb ----------

def imdb_find(title, year_hint):
    q = urllib.parse.quote(title.lower()[:60])
    first = q[0] if q and q[0].isalnum() else "x"
    try:
        res = json.loads(http(f"https://v3.sg.media-imdb.com/suggestion/{first}/{q}.json", tries=3))
    except Exception:
        return None
    cands = [d for d in res.get("d", []) if d.get("id", "").startswith("tt")
             and d.get("qid") in ("movie", "tvMovie", "video", "tvSpecial")]
    if not cands:
        return None
    exact = [d for d in cands if norm(d.get("l")) == norm(title)]
    pool = exact or cands
    if year_hint:
        recent = [d for d in pool if d.get("y") and d["y"] >= year_hint - 1]
        if recent:
            return recent[0]
    return pool[0] if exact else None


def imdb_details(tt):
    q = ('{title(id:"%s"){titleText{text} releaseYear{year} '
         'ratingsSummary{aggregateRating voteCount} '
         'principalCredits{category{id} credits{name{nameText{text}}}}}}' % tt)
    res = json.loads(http("https://caching.graphql.imdb.com/",
                          data=json.dumps({"query": q}).encode(),
                          headers={"Content-Type": "application/json",
                                   "x-imdb-client-name": "imdb-web-next-localized",
                                   "Origin": "https://www.imdb.com",
                                   "Referer": "https://www.imdb.com/"}))
    t = (res.get("data") or {}).get("title") or {}
    credits = {c["category"]["id"]: [x["name"]["nameText"]["text"] for x in c["credits"]]
               for c in t.get("principalCredits") or []}
    rs = t.get("ratingsSummary") or {}
    return {
        "imdb_id": tt, "imdb_url": f"https://www.imdb.com/title/{tt}/",
        "imdb_title": (t.get("titleText") or {}).get("text"),
        "year": (t.get("releaseYear") or {}).get("year"),
        "imdb": rs.get("aggregateRating"), "imdb_votes": rs.get("voteCount"),
        "directors": credits.get("director", [])[:2],
        "actors": credits.get("cast", [])[:3],
    }


# ---------- Rotten Tomatoes ----------

RT_ALGOLIA = ("https://79frdp12pn-dsn.algolia.net/1/indexes/*/queries"
              "?x-algolia-application-id=79FRDP12PN&x-algolia-api-key=175588f6e5f8319b27702e4cc4013561")


def rt_lookup(title, year):
    # RT's own site search index (Algolia). The RT website itself blocks GitHub's servers.
    body = json.dumps({"requests": [{"indexName": "content_rt", "query": title,
                                     "params": "filters=isEmsSearchable%20%3D%201&hitsPerPage=8"}]}).encode()
    try:
        res = json.loads(http(RT_ALGOLIA, data=body, tries=3,
                              headers={"Content-Type": "application/json",
                                       "Referer": "https://www.rottentomatoes.com/"}))
    except Exception as e:
        print("rt fail", title, e)
        return {}
    for h in res["results"][0].get("hits", []):
        if h.get("type") != "movie":
            continue
        if norm(title) not in {norm(t) for t in [h.get("title")] + (h.get("titles") or [])}:
            continue
        ry = h.get("releaseYear")
        if year and ry and abs(ry - year) > 1:
            continue
        score = (h.get("rottenTomatoes") or {}).get("criticsScore")
        return {"rt": score if isinstance(score, int) else None,
                "rt_url": f"https://www.rottentomatoes.com/m/{h['vanity']}" if h.get("vanity") else None}
    return {}


# ---------- notify ----------

def fmt_line(m):
    imdb = f"⭐{m['imdb']:.1f}" if m.get("imdb") else "⭐–"
    rt = f"🍅{m['rt']}%" if m.get("rt") is not None else "🍅–"
    people = []
    if m.get("directors"):
        people.append("🎬 " + ", ".join(m["directors"]))
    if m.get("actors"):
        people.append(", ".join(m["actors"][:2]))
    he = f" ({m['title_he']})" if m.get("title_he") and norm(m["title_he"]) != norm(m["title"]) else ""
    new = "🆕 " if age_days(m) is not None and age_days(m) < 8 else ""
    return f"{new}{imdb} {rt} {m['title']}{he}" + (" · " + " · ".join(people) if people else "")


def age_days(m):
    if not m.get("date_started"):
        return None
    return (datetime.now(IL).date() - datetime.fromisoformat(m["date_started"]).date()).days


def notify(movies):
    topic = os.environ.get("NTFY_TOPIC", "").strip().lstrip("\ufeff")
    if not topic:
        print("NTFY_TOPIC not set, skipping push")
        return
    lines, size = [], 0
    for i, m in enumerate(movies):
        line = fmt_line(m)
        if size + len(line.encode()) > 3700:
            lines.append(f"…ועוד {len(movies) - i} בדף")
            break
        lines.append(line)
        size += len(line.encode()) + 1
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data="\n".join(lines).encode("utf-8"),
        headers={"Title": f"Cinema City this week: {len(movies)} movies".encode("utf-8"),
                 "Click": PAGE_URL, "Tags": "movie_camera", "Markdown": "no"})
    urllib.request.urlopen(req, timeout=30).read()
    print("push sent")


def sort_key(m):
    return (m.get("imdb") is None, -(m.get("imdb") or 0), -(m.get("rt") or -1))


def main():
    now = datetime.now(timezone.utc)
    if "--scheduled" in sys.argv:
        # cron fires several times on Sunday morning (UTC, covering IST and IDT, plus retries if a site
        # rate-limits us); the first successful run at/after 08:00 Israel wins
        local = now.astimezone(IL)
        if local.hour < 8:
            print("before 08:00 Israel time, skipping"); return
        try:
            prev = json.load(open(DATA_PATH, encoding="utf-8"))
            if prev.get("generated_at", "")[:10] == local.date().isoformat():
                print("already ran today"); return
        except Exception:
            pass
    try:
        prev_movies = {norm(x["title"]): x for x in json.load(open(DATA_PATH, encoding="utf-8"))["movies"]}
    except Exception:
        prev_movies = {}
    movies = now_showing(fetch_cinema_city(), now)
    print(f"{len(movies)} movies now showing")
    for m in movies:
        hint = int(m["date_started"][:4]) if m.get("date_started") else None
        try:
            hit = imdb_find(m["title"], hint)
            if hit:
                m.update(imdb_details(hit["id"]))
        except Exception as e:
            print("imdb fail", m["title"], e)
        m.update(rt_lookup(m["title"], m.get("year") or hint))
        old = prev_movies.get(norm(m["title"]), {})
        for k in ("imdb", "imdb_url", "year", "directors", "actors", "rt", "rt_url"):
            if m.get(k) in (None, []) and old.get(k) not in (None, []):
                m[k] = old[k]  # a lookup was blocked this run; keep last week's value
        print(" ", fmt_line(m))
        time.sleep(0.5)
    movies.sort(key=sort_key)
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": now.astimezone(IL).isoformat(timespec="minutes"),
                   "movies": movies}, f, ensure_ascii=False, indent=1)
    if "--no-push" not in sys.argv:
        try:
            notify(movies)
        except Exception as e:
            print("push failed:", e)


if __name__ == "__main__":
    main()
