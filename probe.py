import re, urllib.request, json
H = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20) as r:
            return r.status, r.read(400000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e: return e.code, ""
    except Exception as e: return str(e)[:60], ""
sites = {
 "planet": "https://www.planetcinema.co.il/",
 "planet-api": "https://www.planetcinema.co.il/il/data-api-service/v1/quickbook/10100/cinemas/with-event/until/2026-12-31?attr=&lang=he_IL",
 "rav-hen": "https://www.rav-hen.co.il/",
 "rav-hen-api": "https://www.rav-hen.co.il/il/data-api-service/v1/quickbook/10104/cinemas/with-event/until/2026-12-31?attr=&lang=he_IL",
 "hot": "https://hotcinema.co.il/",
 "lev": "https://www.lev.co.il/",
 "movieland": "https://www.movieland.co.il/",
}
for k, u in sites.items():
    st, body = get(u)
    tech = [t for t in ["wix", "wordpress", "wp-content", "quickbook", "data-api-service", "vista", "next.js", "__NEXT_DATA__", "react", "angular", "graphql", "api/"] if t.lower() in body.lower()]
    extra = ""
    if "api" in k and body.startswith("{"):
        try:
            d = json.loads(body); cs = d.get("body", {}).get("cinemas", [])
            extra = " cinemas: " + ", ".join(c.get("displayName", "") for c in cs)
        except Exception as e: extra = " json?" + str(e)[:40]
    print(k, st, len(body), tech, extra[:600])
