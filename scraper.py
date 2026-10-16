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
# The site is Wix; its pages read two public data collections:
#   SyncPresentations: every screening (movie, cinema, hall type, time) - the source of truth here
#   SyncFeatures: one row per movie (poster, premiere date) - nice to have
# Wix rate-limits these queries, so pages are spaced out and SyncFeatures is optional.

SPECIAL_HALLS = ("Lounge", "ONYX", "VIP", "Prime")
# Oren only goes to the center: nothing north of Netanya or south of Rishon LeZion
CENTRAL = {"גלילות", 'ראשל"צ', "כפר-סבא", "נתניה"}
# opera / ballet / concerts / musicals / stand-up are not movies
NOT_MOVIE_RE = re.compile(r"(^|,)\s*SHOW\s*(,|$)|מופע|הצגה|מחזמר|אופרה|בלט|קונצרט|הופעה|סטנדאפ")

# well-known names for the "big names" filter (matched against IMDb principal credits)
TOP_ACTORS = {
    "Tom Cruise", "Robert Downey Jr.", "Leonardo DiCaprio", "Brad Pitt", "Denzel Washington", "Tom Hanks",
    "Meryl Streep", "Scarlett Johansson", "Margot Robbie", "Matt Damon", "Christian Bale", "Cillian Murphy",
    "Zendaya", "Tom Holland", "Timothée Chalamet", "Florence Pugh", "Emma Stone", "Ryan Gosling",
    "Anne Hathaway", "Dakota Johnson", "Jennifer Lawrence", "Natalie Portman", "Keanu Reeves", "Will Smith",
    "Dwayne Johnson", "Jason Statham", "Vin Diesel", "Chris Hemsworth", "Chris Evans", "Chris Pratt",
    "Mark Wahlberg", "Ryan Reynolds", "Hugh Jackman", "Joaquin Phoenix", "Jake Gyllenhaal", "Austin Butler",
    "Pedro Pascal", "Glen Powell", "Sydney Sweeney", "Jenna Ortega", "Anya Taylor-Joy", "Saoirse Ronan",
    "Nicole Kidman", "Julia Roberts", "Sandra Bullock", "Cate Blanchett", "Charlize Theron", "Angelina Jolie",
    "Johnny Depp", "Harrison Ford", "Samuel L. Jackson", "Morgan Freeman", "Al Pacino", "Robert De Niro",
    "Russell Crowe", "Ethan Hawke", "Jessica Chastain", "Viola Davis", "Emily Blunt", "Robert Pattinson",
    "Kristen Stewart", "Rami Malek", "Oscar Isaac", "Michael B. Jordan", "Daniel Craig", "Idris Elba",
    "Benedict Cumberbatch", "Tom Hardy", "Ralph Fiennes", "Colin Farrell", "Paul Mescal", "Jeremy Allen White",
    "Mikey Madison", "Ana de Armas", "Gal Gadot", "Jamie Lee Curtis", "Kate Winslet", "Adam Driver",
    "Bradley Cooper", "Jonah Hill", "Ben Affleck", "George Clooney", "Owen Wilson", "Ben Stiller",
    "Adam Sandler", "Jim Carrey", "Eddie Murphy", "Kevin Hart", "Steve Carell", "Jack Black",
    "Ewan McGregor", "Helena Bonham Carter", "Brendan Fraser", "Keira Knightley", "Elizabeth Olsen",
    "Rebecca Ferguson", "Josh Brolin", "Woody Harrelson", "Willem Dafoe", "Mads Mikkelsen", "Isabelle Huppert",
    "Riz Ahmed", "Alan Ritchson", "Noah Centineo", "Jodie Comer", "Barry Keoghan", "Andrew Garfield",
}
TOP_DIRECTORS = {
    "Christopher Nolan", "Steven Spielberg", "Martin Scorsese", "Quentin Tarantino", "Denis Villeneuve",
    "Ridley Scott", "James Cameron", "David Fincher", "Greta Gerwig", "Wes Anderson", "Paul Thomas Anderson",
    "Alejandro G. Iñárritu", "Alfonso Cuarón", "Guillermo del Toro", "Bong Joon Ho", "Yorgos Lanthimos",
    "Damien Chazelle", "Jordan Peele", "Taika Waititi", "Sam Mendes", "Darren Aronofsky", "Aaron Sorkin",
    "Ryan Coogler", "James Gunn", "Matt Reeves", "Rian Johnson", "Edgar Wright", "Guy Ritchie",
    "Clint Eastwood", "Spike Lee", "Sofia Coppola", "Kathryn Bigelow", "Joseph Kosinski", "Christopher McQuarrie",
    "Anthony Russo", "Joe Russo", "Chad Stahelski", "Sam Raimi", "Zach Cregger", "David Ayer",
    "Asghar Farhadi", "Pedro Almodóvar", "Luca Guadagnino", "Park Chan-wook", "Jon M. Chu", "Andrew Stanton",
    "Pete Docter", "Danny Boyle", "Steve McQueen", "Barry Jenkins", "Emerald Fennell", "Trey Edward Shults",
    "Nicolas Winding Refn", "Eli Roth", "Michael Showalter", "Destin Daniel Cretton",
}


def wix_query(inst, collection, cursor=None):
    q = {"cursorPaging": {"limit": 1000, "cursor": cursor}} if cursor else {"paging": {"limit": 1000}}
    body = json.dumps({"dataCollectionId": collection, "query": q}).encode()
    res = json.loads(http(f"{SITE}/_api/cloud-data/v2/items/query", data=body, tries=4, wait=30,
                          headers={"Authorization": inst, "Content-Type": "application/json"}))
    meta = res.get("pagingMetadata", {})
    nxt = meta.get("cursors", {}).get("next") if meta.get("hasNext") else None
    return [d["data"] for d in res.get("dataItems", [])], nxt


def fetch_cinema_city():
    tokens = json.loads(http(f"{SITE}/_api/v1/access-tokens", tries=4, wait=30))
    inst = tokens["apps"][WIX_CODE_APP]["instance"]
    pres, cursor = wix_query(inst, "SyncPresentations")
    while cursor:
        time.sleep(12)
        page, cursor = wix_query(inst, "SyncPresentations", cursor)
        pres += page
    try:
        time.sleep(12)
        feats = {str(f.get("externalId")): f for f in wix_query(inst, "SyncFeatures")[0]}
    except Exception as e:
        print("SyncFeatures unavailable, using last week's posters/dates:", e)
        feats = {}
    out = []
    for row in pres:  # hall type (venueTypeName) lives on the row, the rest in payloadJson
        p = json.loads(row["payloadJson"]) if isinstance(row.get("payloadJson"), str) else dict(row.get("payloadJson") or {})
        p.setdefault("venueTypeName", row.get("venueTypeName"))
        out.append(p)
    return out, feats


def short_loc(name):
    return (name or "").replace("סינמה סיטי", "").strip(" -")


def now_showing(pres, feats, now):
    today = now.astimezone(IL).date()
    last = today + timedelta(days=6)
    movies = {}
    for p in pres:
        en = (p.get("featureAdditionalName") or "").strip()
        he = (p.get("featureName") or "").strip()
        day = datetime.fromisoformat(p["businessDate"][:10]).date()
        if p.get("featureTypeId") != 1 or not en or not (today <= day <= last):
            continue  # events, or not this week
        if NOT_MOVIE_RE.search(p.get("featureCategoryName") or "") or NOT_MOVIE_RE.search(he):
            continue
        if short_loc(p.get("locationName")) not in CENTRAL:
            continue
        if FOREIGN_DUB_RE.search(he) or re.search(r"[\u0400-\u04ff]", en):
            continue  # Russian/French dubs duplicate the main entry
        version = (VERSION_RE.search(he).group(1) if VERSION_RE.search(he) else "")
        if version.startswith("Infinity"):
            version = "Infinity Vision"
        fid = str(p.get("featureId"))
        f = feats.get(fid, {})
        m = movies.setdefault(norm(en), {
            "title": en, "title_he": VERSION_RE.sub("", he).strip(), "cc_id": fid,
            "cc_url": f"{SITE}/movie/{fid}", "poster": f.get("image"),
            "genre": p.get("featureCategoryName") or "", "duration": p.get("durationInMinutes"),
            "language": None, "kids": "KIDSHOW" in (p.get("featureCategoryName") or ""),
            "date_started": (f.get("payloadJson") or {}).get("dateStarted"),
            "versions": [], "has_original": False, "next_show": p["dateTime"],
            "screenings": 0, "cinemas": set(), "halls": {},
        })
        dubbed = version.startswith("מדובב") or bool(p.get("dubbedLanguageISO"))
        if not dubbed:
            m["has_original"] = True
            m["language"] = m["language"] or p.get("languageISO")
            if not version:  # link to the original-language entry when there is one
                m["cc_id"], m["cc_url"] = fid, f"{SITE}/movie/{fid}"
                m["poster"] = f.get("image") or m["poster"]
                m["date_started"] = (f.get("payloadJson") or {}).get("dateStarted") or m["date_started"]
        if version and version not in m["versions"]:
            m["versions"].append(version)
        m["screenings"] += 1
        m["cinemas"].add(short_loc(p.get("locationName")))
        m["next_show"] = min(m["next_show"], p["dateTime"])
        hall = "Infinity Vision" if version == "Infinity Vision" else p.get("venueTypeName")
        if hall in SPECIAL_HALLS + ("Infinity Vision",):
            m["halls"].setdefault(hall, set()).add(short_loc(p.get("locationName")))
    for m in movies.values():
        m["cinemas"] = sorted(m["cinemas"])
        m["halls"] = {k: sorted(v) for k, v in sorted(m["halls"].items())}
        m["versions"] = [v for v in m["versions"] if v != "Infinity Vision"]
        m["genre"] = ", ".join(g for g in m["genre"].split(",") if g and "SHOW" not in g)
        m["foreign"] = bool(m["language"]) and m["language"] not in ("en", "he")
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


def is_leaving(m, now):
    """Signs a movie is on its way out: far fewer screenings than last week, or an old movie in few places."""
    prev, cur, age = m.get("prev_screenings"), m["screenings"], age_days(m)
    if prev and cur <= prev * 0.5:
        return True
    return age is not None and age >= 28 and (cur <= 12 or len(m["cinemas"]) <= 1)


def sort_key(m):
    return (m.get("imdb") is None, -(m.get("imdb") or 0), -(m.get("rt") or -1))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
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
    pres, feats = fetch_cinema_city()
    movies = now_showing(pres, feats, now)
    print(f"{len(movies)} movies now showing")
    for m in movies:
        hint = int(m["date_started"][:4]) if m.get("date_started") else None
        hit = None
        try:
            hit = imdb_find(m["title"], hint)
            if hit:
                m.update(imdb_details(hit["id"]))
        except Exception as e:
            print("imdb fail", m["title"], e)
        m.update(rt_lookup(m["title"], m.get("year") or hint))
        old = prev_movies.get(norm(m["title"]), {})
        for k in ("imdb", "imdb_url", "year", "directors", "actors", "rt", "rt_url", "poster", "date_started"):
            if m.get(k) in (None, []) and old.get(k) not in (None, []):
                m[k] = old[k]  # a lookup was blocked this run; keep last week's value
        m["top_people"] = [p for p in m.get("directors") or [] if p in TOP_DIRECTORS] + \
                          [p for p in m.get("actors") or [] if p in TOP_ACTORS]
        m["prev_screenings"] = old.get("screenings")
        m["leaving"] = is_leaving(m, now)
        if not m.get("poster") and hit and hit.get("i"):
            m["poster"] = hit["i"]["imageUrl"].replace("._V1_.", "._V1_UX300_.")
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
