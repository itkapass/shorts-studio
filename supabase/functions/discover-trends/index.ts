// discover-trends/index.ts
//
// Backs the Admin Panel's "Trending Radar" page. THIS REPLACES A MOCK: the
// previous version was a fixed array of 6 hardcoded example topics (Titan,
// NVIDIA, Rolex, Apple, Costco, De Beers) with invented "viral_score" and
// "$26 CPM" numbers. The "Refresh Hot Trends" button didn't call anything —
// it just spun a loading icon for 800ms and stopped.
//
// This function calls YouTube Data API's search.list + videos.list (a
// read-only API-key auth, separate and much simpler than the OAuth flow
// used for uploading — see docs/04) to surface REAL recently-popular Shorts
// for a category keyword: real titles, real channels, real view counts.
// No invented scores. If you don't have a YOUTUBE_API_KEY configured, this
// returns a clear error explaining what to add rather than silently
// falling back to fake data.
//
// Deploy: supabase functions deploy discover-trends
// Secret:  supabase secrets set YOUTUBE_API_KEY=...
import { requireUser, jsonResponse, CORS_HEADERS } from "../_shared/auth.ts";

const DEFAULT_CATEGORIES = ["technology explained", "business breakdown", "science facts"];

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });

  const { user, error: authError } = await requireUser(req);
  if (!user) return jsonResponse({ error: authError }, 401);

  const apiKey = Deno.env.get("YOUTUBE_API_KEY");
  if (!apiKey) {
    return jsonResponse({
      error: "YOUTUBE_API_KEY is not configured. This is a separate, simpler API key than the " +
        "OAuth credentials used for publishing — see docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md. " +
        "Create one in the same Google Cloud project (APIs & Services -> Credentials -> Create API Key), " +
        "restrict it to the YouTube Data API v3, then run: supabase secrets set YOUTUBE_API_KEY=...",
    }, 424);
  }

  try {
    const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
    const categories: string[] = Array.isArray(body.categories) && body.categories.length
      ? body.categories
      : DEFAULT_CATEGORIES;

    const publishedAfter = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    const results: Record<string, unknown>[] = [];

    for (const category of categories) {
      const searchUrl = new URL("https://www.googleapis.com/youtube/v3/search");
      searchUrl.search = new URLSearchParams({
        key: apiKey, part: "snippet", type: "video", order: "viewCount",
        videoDuration: "short", publishedAfter, q: category, maxResults: "5",
      }).toString();

      const searchResp = await fetch(searchUrl);
      if (!searchResp.ok) {
        const errText = await searchResp.text();
        return jsonResponse({ error: `YouTube search failed (${searchResp.status}): ${errText}` }, 502);
      }
      const searchData = await searchResp.json();
      const ids = (searchData.items ?? []).map((it: any) => it.id?.videoId).filter(Boolean);
      if (!ids.length) continue;

      const statsUrl = new URL("https://www.googleapis.com/youtube/v3/videos");
      statsUrl.search = new URLSearchParams({
        key: apiKey, part: "snippet,statistics", id: ids.join(","),
      }).toString();
      const statsResp = await fetch(statsUrl);
      if (!statsResp.ok) continue;
      const statsData = await statsResp.json();

      for (const v of statsData.items ?? []) {
        results.push({
          category,
          video_id: v.id,
          title: v.snippet?.title,
          channel: v.snippet?.channelTitle,
          published_at: v.snippet?.publishedAt,
          view_count: v.statistics?.viewCount ? Number(v.statistics.viewCount) : null,
          thumbnail: v.snippet?.thumbnails?.medium?.url ?? v.snippet?.thumbnails?.default?.url,
          url: `https://www.youtube.com/watch?v=${v.id}`,
        });
      }
    }

    results.sort((a, b) => (Number(b.view_count) || 0) - (Number(a.view_count) || 0));
    return jsonResponse({ results, note: "Real YouTube search results from the last 7 days — not a prediction or score, just what's actually getting views right now." });
  } catch (e: unknown) {
    return jsonResponse({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
