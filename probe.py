# one-off: copy every poster (this week, upcoming, archive) into docs/posters, using fresh Cinema City links
import json, sys, time
sys.path.insert(0, ".")
import scraper as s
tokens = json.loads(s.http(f"{s.SITE}/_api/v1/access-tokens", tries=2, wait=20))
inst = tokens["apps"][s.WIX_CODE_APP]["instance"]
feats = {str(f.get("externalId")): f for f in s.wix_query(inst, "SyncFeatures")[0]}
d = json.load(open(s.DATA_PATH, encoding="utf-8"))
archive = json.load(open(s.ARCHIVE_PATH, encoding="utf-8"))
def fix(m):
    cc_id = (m.get("cc_url") or "").rsplit("/", 1)[-1]
    fresh = (feats.get(cc_id) or {}).get("image")
    if fresh:
        m["poster"] = fresh
    if not m.get("imdb_poster"):
        hit = s.imdb_find(m.get("imdb_title") or m["title"], m.get("year"))
        if hit and hit.get("i"):
            m["imdb_poster"] = hit["i"]["imageUrl"].replace("._V1_.", "._V1_UX500_.")
        time.sleep(0.3)
    s.mirror_poster(m)
    print(m["title"], "->", m["poster"][:60])
for m in d["movies"] + d.get("upcoming", []):
    fix(m)
for m in archive.values():
    fix(m)
json.dump(d, open(s.DATA_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(archive, open(s.ARCHIVE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
