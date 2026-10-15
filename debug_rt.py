import re, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode()
for t in ["Toy Story 5", "Madama Butterfly", "Matchmaking 3", "The Bay", "Primavera"]:
    p = get("https://www.rottentomatoes.com/search?search=" + urllib.parse.quote(t))
    sec = re.search(r'<search-page-result[^>]*type="movie"[^>]*>(.*?)</search-page-result>', p, re.S)
    print("==", t, "section:", bool(sec))
    if sec:
        for row in re.findall(r"<search-page-media-row(.*?)</search-page-media-row>", sec.group(1), re.S)[:4]:
            print("  ", re.sub(r"\s+", " ", row)[:600])
p = get("https://www.rottentomatoes.com/m/toy_story_5")
for k in ["criticsScore", "tomatometer", "scoreboard", "ratingValue", "audienceScore"]:
    i = p.find(k); print(k, i, re.sub(r"\s+", " ", p[i-50:i+250]) if i >= 0 else "")
