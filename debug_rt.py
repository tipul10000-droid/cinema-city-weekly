import json, re, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
def get(u, data=None, h=None):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, data=data, headers={"User-Agent": UA, **(h or {})}), timeout=40); return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:300]
    except Exception as e: return 0, str(e)
body = json.dumps({"requests": [{"indexName": "content_rt", "query": "Toy Story 5", "params": "filters=isEmsSearchable%20%3D%201&hitsPerPage=3"}]}).encode()
c, p = get("https://79frdp12pn-dsn.algolia.net/1/indexes/*/queries?x-algolia-application-id=79FRDP12PN&x-algolia-api-key=175588f6e5f8319b27702e4cc4013561", body, {"Content-Type": "application/json", "Referer": "https://www.rottentomatoes.com/"})
print("algolia", c, p[:1500])
c, p = get("https://r.jina.ai/https://www.rottentomatoes.com/m/toy_story_5")
print("jina", c, p[:1200])
