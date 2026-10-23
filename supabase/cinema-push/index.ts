// Web push and per-user marks for the Cinema City weekly page. Deployed as a Supabase Edge Function
// ("cinema-push") in the family-apps project, next to the sandwich app's send-reminders.
// Users: oren, lior, evyatar (shared password, kept in cinema_secrets.user_password) and guest (no password,
// no marks). Nobody sees anyone else's marks, except that Oren sees what Lior and Evyatar want to watch.
//   GET  ?action=pubkey             -> VAPID public key for the page
//   POST ?action=login              -> {user, pass} -> ok or 401
//   POST ?action=subscribe          -> {sub, user, pass}: store a PushSubscription for that user (guest without pass)
//   POST ?action=unsubscribe        -> {endpoint}: forget that device
//   GET  ?action=prefs&user=        -> (x-cinema-pass header) own favorites/watched; Oren also gets the others' favorites
//   POST ?action=prefs&user=        -> save own marks; a new favorite from Lior/Evyatar pushes a note to Oren
//   POST ?action=send               -> push the latest scan (docs/data.json on main) to every subscriber, once per scan,
//                                      tailored to each user's taste, plus premieres and leaving-soon favorites
import webpush from "npm:web-push@3.6.7";
import { createClient } from "npm:@supabase/supabase-js@2";

const PAGE_URL = "https://tipul10000-droid.github.io/cinema-city-weekly/";
// GitHub API (not raw.githubusercontent) so a just-committed scan is never served from cache
const DATA_URL = "https://api.github.com/repos/tipul10000-droid/cinema-city-weekly/contents/docs/data.json?ref=main";
const USERS = ["oren", "lior", "evyatar"];
const NAMES: Record<string, string> = { oren: "אורן", lior: "ליאור", evyatar: "אביתר", guest: "אורח" };
// Lior likes romantic comedies, romance, drama and "special" films (e.g. Verity, Heart of the Beast);
// Oren and Evyatar share a taste: everything for grown-ups
const TASTE: Record<string, (m: any) => boolean> = {
  lior: (m) => !m.kids && /רומנט|קומדי|דרמה|מותחן/.test(m.genre || ""),
};
const forUser = (user: string) => TASTE[user] || ((m: any) => !m.kids);

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-cinema-pass",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};
const json = (o: unknown, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json", ...CORS } });

async function secrets(sb: any) {
  const { data } = await sb.from("cinema_secrets").select("name,value");
  const map: Record<string, string> = {};
  (data || []).forEach((r: any) => (map[r.name] = r.value));
  return map;
}

// VAPID key pair is generated server-side on first use and kept in a locked table.
async function getKeys(sb: any, map: Record<string, string>) {
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
const dm = (iso: string) => { const [, mo, d] = iso.slice(0, 10).split("-"); return `${+d}.${+mo}`; };

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
  const url = new URL(req.url);
  const action = url.searchParams.get("action");
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const map = await secrets(sb);
  const keys = await getKeys(sb, map);
  webpush.setVapidDetails(PAGE_URL, keys.pub, keys.priv);
  const authed = (user: unknown, pass: unknown) =>
    typeof user === "string" && USERS.includes(user) && !!map.user_password && pass === map.user_password;

  if (action === "pubkey") return json({ publicKey: keys.pub });

  if (action === "login" && req.method === "POST") {
    const b = await req.json().catch(() => ({}));
    return authed(b.user, b.pass) ? json({ ok: true }) : json({ ok: false }, 401);
  }

  if (action === "prefs") {
    const user = url.searchParams.get("user");
    if (!authed(user, req.headers.get("x-cinema-pass"))) return json({ ok: false }, 401);
    const { data: row } = await sb.from("cinema_prefs").select("fav,seen").eq("id", user).maybeSingle();
    if (req.method === "POST") {
      const b = await req.json().catch(() => null);
      const clean = (a: unknown) => Array.isArray(a) ? [...new Set(a.filter((x) => typeof x === "string" && x.length < 200))].slice(0, 2000) : [];
      if (!b) return json({ ok: false }, 400);
      const fav = clean(b.fav), seen = clean(b.seen);
      await sb.from("cinema_prefs").upsert({ id: user, fav, seen, updated_at: new Date().toISOString() });
      // Lior or Evyatar wants to watch something: tell Oren
      const added = fav.filter((t) => !(row?.fav || []).includes(t));
      if (user !== "oren" && added.length) {
        const { data: subs } = await sb.from("cinema_push").select("*").eq("user_id", "oren");
        await push(sb, subs || [], {
          title: `★ ${NAMES[user!]} רוצה לראות`,
          body: added.join(", "),
          url: PAGE_URL, tag: `cinema-fav-${user}-${Date.now()}`,
        });
      }
      return json({ ok: true });
    }
    const out: any = { prefs: { fav: row?.fav || [], seen: row?.seen || [] } };
    if (user === "oren") {  // only Oren sees the others' favorites (never their watched list)
      const { data: rows } = await sb.from("cinema_prefs").select("id,fav").in("id", ["lior", "evyatar"]);
      out.others = Object.fromEntries((rows || []).map((r: any) => [r.id, r.fav || []]));
    }
    return json(out);
  }

  if (action === "subscribe" && req.method === "POST") {
    const b = await req.json().catch(() => null);
    const s = b?.sub || b;  // older pages posted the bare subscription
    if (!s?.endpoint?.startsWith("https://") || !s?.keys?.p256dh || !s?.keys?.auth) return json({ ok: false }, 400);
    const user = authed(b?.user, b?.pass) ? b.user : "guest";
    const row = { endpoint: s.endpoint, p256dh: s.keys.p256dh, auth: s.keys.auth, user_id: user };
    await sb.from("cinema_push").upsert(row);
    const sent = await push(sb, [row], {
      title: `🎬 ההתראות פעילות · ${NAMES[user] || "אורח"}`,
      body: user === "oren"
        ? "סרטים חדשים, בכורות, ומה שליאור ואביתר מסמנים ★"
        : "כל יום ראשון: מה חדש בסינמה סיטי, ובכורות גדולות כשהן מגיעות",
      url: PAGE_URL, tag: "cinema-welcome",
    });
    return json({ ok: true, sent, user });
  }

  if (action === "unsubscribe" && req.method === "POST") {
    const b = await req.json().catch(() => null);
    if (!b?.endpoint?.startsWith("https://")) return json({ ok: false }, 400);
    await sb.from("cinema_push").delete().eq("endpoint", b.endpoint);
    return json({ ok: true });
  }

  if (action === "send" && req.method === "POST") {
    const data = await (await fetch(DATA_URL, { headers: { Accept: "application/vnd.github.raw+json", "User-Agent": "cinema-push" } })).json();
    // once per scan, however many times this is called
    const { error: dup } = await sb.from("cinema_push_log").insert({ generated_at: data.generated_at, sent: 0 });
    if (dup) return json({ ok: true, result: "already_sent", generated_at: data.generated_at });
    const movies = data.movies || [];
    const { data: subs } = await sb.from("cinema_push").select("*");
    const { data: prefRows } = await sb.from("cinema_prefs").select("id,fav,seen");
    const prefs = Object.fromEntries((prefRows || []).map((r: any) => [r.id, r]));
    const scanDay = data.generated_at.slice(0, 10);
    const weekEnd = new Date(Date.parse(scanDay) + 7 * 864e5).toISOString().slice(0, 10);
    // big premieres (200K+ IMDb watchlist, the page's default bar) opening this week, and blockbusters newly
    // announced since the last scan; data.upcoming holds every announced movie
    const BIG = 200_000;
    const allUpcoming = data.upcoming || [];
    const upcoming = allUpcoming.filter((m: any) => (m.watchlist || 0) >= BIG);
    const openingNow = upcoming.filter((m: any) => m.date_started >= scanDay && m.date_started < weekEnd);
    const known = new Set(JSON.parse(map.upcoming_known || "[]"));
    const announced = map.upcoming_known ? upcoming.filter((m: any) => !known.has(m.title)) : [];
    await sb.from("cinema_secrets").upsert({ name: "upcoming_known", value: JSON.stringify([...known, ...upcoming.map((m: any) => m.title)]) });

    let sent = 0;
    for (const user of [...USERS, "guest"]) {
      const mine = (subs || []).filter((s: any) => s.user_id === user);
      if (!mine.length) continue;
      const list = movies.filter(forUser(user));
      const premieres = list.filter((m: any) => m.premiere_week).map((m: any) => m.title);
      const head = [
        openingNow.length ? `🎬 בכורה גדולה השבוע: ${openingNow.map((m: any) => `${m.title} (${dm(m.date_started)})`).join(", ")}` : "",
        announced.length ? `📅 חדש ברשימת הבקרוב: ${announced.map((m: any) => `${m.title} (${dm(m.date_started)})`).join(", ")}` : "",
        premieres.length ? `🆕 בכורות השבוע: ${premieres.join(", ")}` : "",
      ].filter(Boolean).join("\n");
      sent += await push(sb, mine, {
        title: user === "guest" ? `🎬 סינמה סיטי השבוע: ${movies.length} סרטים` : `🎬 ${NAMES[user]}, מה בסינמה סיטי השבוע`,
        body: (head ? head + "\n\n" : "") + list.slice(0, 10).map(line).join("\n") + (list.length > 10 ? `\n…ועוד ${list.length - 10} בדף` : ""),
        url: PAGE_URL, tag: `cinema-${data.generated_at}`,
      });
      const p = prefs[user];
      if (!p) continue;
      const fav = new Set(p.fav || []), seen = new Set(p.seen || []);
      // movies this user starred before they came out, opening this week
      const starred = allUpcoming.filter((m: any) => fav.has(m.title) && m.date_started >= scanDay && m.date_started < weekEnd);
      if (starred.length) {
        await push(sb, mine, {
          title: starred.length === 1 ? `★ ${starred[0].title} יוצא השבוע` : `★ ${starred.length} סרטים שסימנת יוצאים השבוע`,
          body: starred.map((m: any) => `${m.title}${m.title_he ? ` (${m.title_he})` : ""}: בכורה ב-${dm(m.date_started)}`).join("\n"),
          url: PAGE_URL, tag: `cinema-starred-${data.generated_at}`,
        });
      }
      const leaving = movies.filter((m: any) => m.leaving && fav.has(m.title) && !seen.has(m.title));
      if (leaving.length) {
        await push(sb, mine, {
          title: leaving.length === 1 ? `⏳ ${leaving[0].title} עומד לרדת מהמסכים` : `⏳ ${leaving.length} סרטים מהמועדפים עומדים לרדת`,
          body: leaving.map((m: any) => `${m.title}: ${m.screenings} הקרנות השבוע${m.prev_screenings ? ` (היו ${m.prev_screenings})` : ""}, ${(m.cinemas || []).join(", ")}`).join("\n"),
          url: PAGE_URL, tag: `cinema-leaving-${data.generated_at}`,
        });
      }
    }
    await sb.from("cinema_push_log").update({ sent }).eq("generated_at", data.generated_at);
    return json({ ok: true, sent, subscribers: (subs || []).length, opening: openingNow.length, announced: announced.length });
  }

  return json({ ok: false, error: "unknown action" }, 400);
});
