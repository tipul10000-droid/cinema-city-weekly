import json, sys
sys.path.insert(0, ".")
import scraper
def gql(q):
    try:
        return scraper.http("https://caching.graphql.imdb.com/", data=json.dumps({"query": q}).encode(),
            headers={"Content-Type": "application/json", "x-imdb-client-name": "imdb-web-next-localized",
                     "Origin": "https://www.imdb.com", "Referer": "https://www.imdb.com/"})
    except Exception as e:
        return f"ERR {e} {getattr(e,'read',lambda:b'')()[:2000]}"
print("=== comingSoon IL")
print(gql('{comingSoon(first:100, comingSoonType:MOVIE, regionOverride:"IL", releasingOnOrAfter:"2026-10-22", releasingOnOrBefore:"2026-12-31"){total edges{node{id titleText{text} releaseDate{day month year} meterRanking{currentRank} ratingsSummary{voteCount} engagementStatistics{watchlistStatistics{displayableCount{text}}}}}}}')[:20000])
print("=== comingSoon default")
print(gql('{comingSoon(first:30, comingSoonType:MOVIE, releasingOnOrAfter:"2026-10-22", releasingOnOrBefore:"2026-12-31"){total edges{node{id titleText{text} releaseDate{day month year} meterRanking{currentRank}}}}}')[:6000])
print("=== releaseDates for Dune")
print(gql('{title(id:"tt31378509"){titleText{text} releaseDates(first:60){edges{node{country{id} day month year}}}}}')[:4000])
print("=== cinema city features")
try:
    tokens = json.loads(scraper.http(f"{scraper.SITE}/_api/v1/access-tokens", tries=2, wait=20))
    inst = tokens["apps"][scraper.WIX_CODE_APP]["instance"]
    feats, _ = scraper.wix_query(inst, "SyncFeatures")
    print(len(feats))
    rows = []
    for f in feats:
        p = f.get("payloadJson") or {}
        if isinstance(p, str): p = json.loads(p)
        rows.append((p.get("dateStarted") or "", f.get("title") or f.get("name"), list(f.keys())[:30], {k: v for k, v in p.items() if not isinstance(v, (list, dict))}))
    rows.sort(key=lambda r: r[0])
    for r in rows[-40:]: print(json.dumps(r, ensure_ascii=False)[:700])
except Exception as e:
    print("CC ERR", e)
