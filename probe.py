import json, urllib.request, uuid
API = "https://emgtyfksnofzzlutngbf.supabase.co/functions/v1/cinema-push"
def call(q, body=None):
    req = urllib.request.Request(API + q, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req) as r: return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:200]
pid = "00000000-0000-4000-8000-000000000000"
print("bad id", call("?action=pprefs&id=x"))
print("get", call(f"?action=pprefs&id={pid}"))
print("post", call(f"?action=pprefs&id={pid}", {"fav": ["PROBE"], "seen": []}))
print("get2", call(f"?action=pprefs&id={pid}"))
print("post clear", call(f"?action=pprefs&id={pid}", {"fav": [], "seen": []}))
print("family no pass", call("?action=prefs&user=oren"))
print("pubkey", call("?action=pubkey")[0])
