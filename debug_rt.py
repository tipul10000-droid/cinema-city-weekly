import re, time, urllib.request, urllib.parse
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
def get(u, h):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=30); return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, ""
for name, h in [("ua-only", {"User-Agent": H["User-Agent"]}), ("full", H)]:
    for t in ["Toy Story 5", "Verity", "Madama Butterfly"]:
        c, p = get("https://www.rottentomatoes.com/search?search=" + urllib.parse.quote(t), h)
        n = len(re.findall("search-page-media-row", p)); print(name, t, c, n); time.sleep(1)
c, p = get("https://www.rottentomatoes.com/m/toy_story_5", H); print("direct", c, len(p))
for k in ['"aggregateRating"', "criticsScore", "tomatometer-score", "ratingValue"]:
    i = p.find(k); print(k, i, re.sub(r"\s+", " ", p[max(0,i-80):i+300]) if i >= 0 else "")
c, p = get("https://www.rottentomatoes.com/search?search=Toy%20Story%205", H)
sec = re.search(r'<search-page-result[^>]*type="movie"[^>]*>(.*?)</search-page-result>', p, re.S)
for row in re.findall(r"<search-page-media-row(.*?)</search-page-media-row>", sec.group(1) if sec else "", re.S)[:3]: print("ROW", re.sub(r"\s+", " ", row)[:700])
