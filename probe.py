# one-off: add the upcoming-hits list to the current data.json without rescanning screenings or notifying
import json, sys
from datetime import datetime, timezone
sys.path.insert(0, ".")
import scraper as s
tokens = json.loads(s.http(f"{s.SITE}/_api/v1/access-tokens", tries=2, wait=20))
inst = tokens["apps"][s.WIX_CODE_APP]["instance"]
feats = {str(f.get("externalId")): f for f in s.wix_query(inst, "SyncFeatures")[0]}
d = json.load(open(s.DATA_PATH, encoding="utf-8"))
d["upcoming"] = s.upcoming_hits(feats, datetime.now(timezone.utc), [])
json.dump(d, open(s.DATA_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
