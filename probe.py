import json, urllib.request
API = "https://emgtyfksnofzzlutngbf.supabase.co/functions/v1/cinema-push"
def call(q, body=None, headers={}):
    req = urllib.request.Request(API + q, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:200]
print("login ok", call("?action=login", {"user": "oren", "pass": "1121"}))
print("login bad", call("?action=login", {"user": "oren", "pass": "1"}))
print("login guest", call("?action=login", {"user": "guest", "pass": "1121"}))
print("prefs oren", call("?action=prefs&user=oren", headers={"x-cinema-pass": "1121"}))
print("prefs lior", call("?action=prefs&user=lior", headers={"x-cinema-pass": "1121"}))
print("prefs nopass", call("?action=prefs&user=oren"))
print("prefs old client", call("?action=prefs"))
