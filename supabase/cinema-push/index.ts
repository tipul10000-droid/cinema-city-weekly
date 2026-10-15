// Web push for the Cinema City weekly page. Deployed as a Supabase Edge Function ("cinema-push")
// in the family-apps project, next to the sandwich app's send-reminders.
//   GET  ?action=pubkey     -> VAPID public key for the page
//   POST ?action=subscribe  -> store a PushSubscription, send a confirmation push to it
//   POST ?action=send       -> push the latest scan (docs/data.json on main) to every subscriber, once per scan
import webpush from "npm:web-push@3.6.7";
import { createClient } from "npm:@supabase/supabase-js@2";

const PAGE_URL = "https://tipul10000-droid.github.io/cinema-city-weekly/";
// GitHub API (not raw.githubusercontent) so a just-committed scan is never served from cache
const DATA_URL = "https://api.github.com/repos/tipul10000-droid/cinema-city-weekly/contents/docs/data.json?ref=main";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};
const json = (o: unknown, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json", ...CORS } });

// VAPID key pair is generated server-side on first use and kept in a locked table.
async function getKeys(sb: any) {
  const { data } = await sb.from("cinema_secrets").select("name,value").in("name", ["vapid_public", "vapid_private"]);
  const map: Record<string, string> = {};
  (data || []).forEach((r: any) => (map[r.name] = r.value));
  if (map.vapid_public && map.vapid_private) return { pub: map.vapid_public, priv: map.vapid_private };
  const k = webpush.generateVAPIDKeys();
  await sb.from("cinema_secrets").upsert([
    { name: "vapid_public", value: k.publicKey },
    { name: "vapid_private", value: k.privateKey },
  ]);
  return { pub: k.publicKey, priv: k.privateKey };
}

function line(m: any) {
  const imdb = m.imdb ? `⭐${m.imdb.toFixed(1)}` : "⭐–";
  const rt = m.rt != null ? `🍅${m.rt}%` : "🍅–";
  const who = [m.directors?.[0], ...(m.actors || []).slice(0, 2)].filter(Boolean).join(", ");
  return `${imdb} ${rt} ${m.title}${who ? ` · ${who}` : ""}`;
}

async function push(sb: any, subs: any[], payload: object) {
  let sent = 0;
  await Promise.allSettled(subs.map(async (s: any) => {
    try {
      await webpush.sendNotification(
        { endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } },
        JSON.stringify(payload),
        { TTL: 24 * 3600 },
      );
      sent++;
    } catch (e: any) {
      if (e?.statusCode === 404 || e?.statusCode === 410) await sb.from("cinema_push").delete().eq("endpoint", s.endpoint);
    }
  }));
  return sent;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  const action = new URL(req.url).searchParams.get("action");
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const keys = await getKeys(sb);
  webpush.setVapidDetails(PAGE_URL, keys.pub, keys.priv);

  if (action === "pubkey") return json({ publicKey: keys.pub });

  if (action === "subscribe" && req.method === "POST") {
    const s = await req.json().catch(() => null);
    if (!s?.endpoint?.startsWith("https://") || !s?.keys?.p256dh || !s?.keys?.auth) return json({ ok: false }, 400);
    const row = { endpoint: s.endpoint, p256dh: s.keys.p256dh, auth: s.keys.auth };
    await sb.from("cinema_push").upsert(row);
    const sent = await push(sb, [row], {
      title: "🎬 ההתראות פעילות",
      body: "כל יום ראשון ב-08:00 תקבל כאן את רשימת הסרטים בסינמה סיטי",
      url: PAGE_URL, tag: "cinema-welcome",
    });
    return json({ ok: true, sent });
  }

  if (action === "send" && req.method === "POST") {
    const data = await (await fetch(DATA_URL, { headers: { Accept: "application/vnd.github.raw+json", "User-Agent": "cinema-push" } })).json();
    // once per scan, however many times this is called
    const { error: dup } = await sb.from("cinema_push_log").insert({ generated_at: data.generated_at, sent: 0 });
    if (dup) return json({ ok: true, result: "already_sent", generated_at: data.generated_at });
    const movies = data.movies || [];
    const top = movies.slice(0, 12).map(line).join("\n");
    const { data: subs } = await sb.from("cinema_push").select("*");
    const sent = await push(sb, subs || [], {
      title: `🎬 סינמה סיטי השבוע: ${movies.length} סרטים`,
      body: top + (movies.length > 12 ? `\n…ועוד ${movies.length - 12} בדף` : ""),
      url: PAGE_URL, tag: `cinema-${data.generated_at}`,
    });
    await sb.from("cinema_push_log").update({ sent }).eq("generated_at", data.generated_at);
    return json({ ok: true, sent, subscribers: (subs || []).length });
  }

  return json({ ok: false, error: "unknown action" }, 400);
});
