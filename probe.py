import json, sys, time
sys.path.insert(0, ".")
import scraper as s
names = ["Avengers: Doomsday","Dune: Part Three","The Hunger Games: Sunrise on the Reaping","Wicker","Wildwood","Ramayana: Rise of a Legend","Hexed","The Cat In The Hat","Focker In-Law","Paper Tiger","THE FIX","Wild Horse Nine","Ebenezer","I Play Rocky","How to Rob a Bank","VIOLENT NIGHT 2","The Odyssey","Spider-Man: Brand New Day"]
for n in names:
    hit = s.imdb_find(n, 2026)
    if not hit: print(n, "no hit"); continue
    q = ('{title(id:"%s"){titleText{text} meterRanking{currentRank} '
         'engagementStatistics{watchlistStatistics{displayableCount{text}}} '
         'productionBudget{budget{amount currency}}}}' % hit["id"])
    try:
        r = s.http("https://caching.graphql.imdb.com/", data=json.dumps({"query": q}).encode(),
            headers={"Content-Type": "application/json", "x-imdb-client-name": "imdb-web-next-localized", "Origin": "https://www.imdb.com", "Referer": "https://www.imdb.com/"})
        print(n, r[:400])
    except Exception as e:
        print(n, "ERR", getattr(e, "read", lambda: b"")()[:400])
    time.sleep(0.3)
