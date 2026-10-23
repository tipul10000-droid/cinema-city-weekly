import json, urllib.request, time
d = json.load(open("docs/data.json"))
items = d["movies"] + d.get("upcoming", [])
for m in items:
    u = m.get("poster")
    for ua in ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", None):
        try:
            h = {"User-Agent": ua} if ua else {}
            r = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20)
            body = r.read()
            print(r.status, r.headers.get("Content-Type"), len(body), m["title"], "ua" if ua else "noua")
        except Exception as e:
            print("ERR", getattr(e, "code", e), m["title"], "ua" if ua else "noua")
