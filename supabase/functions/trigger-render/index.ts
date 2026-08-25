// trigger-render/index.ts
//
// NEW: closes the "do I need my own computer" gap. Rendering a storyboard
// built in the Create Video page used to only be possible by copying a
// command and running it locally (needs Python, ffmpeg, and your API keys
// on that machine). This function lets the Admin Panel — deployed to
// Vercel, reachable from anywhere — trigger the SAME render as a GitHub
// Actions run instead (.github/workflows/render-on-demand.yml), using
// compute GitHub already gives you for free. The video shows up in the
// Video Queue when the workflow finishes, same as scheduled videos do.
//
// A GitHub PAT with permission to trigger workflow runs is a real
// credential — same reasoning as GEMINI_API_KEY and YOUTUBE_API_KEY:
// it stays server-side as an Edge Function secret, never in the browser.
// Use a fine-grained PAT scoped to ONLY this one repo, with "Actions:
// read and write" permission and nothing else.
//
// Deploy: supabase functions deploy trigger-render
// Secrets:
//   supabase secrets set GITHUB_PAT=github_pat_...
//   supabase secrets set GITHUB_REPO=your-username/your-repo-name
//   supabase secrets set GITHUB_REF=main   # optional, defaults to main
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { requireUser, jsonResponse, CORS_HEADERS } from "../_shared/auth.ts";

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });

  const { user, error: authError } = await requireUser(req);
  if (!user) return jsonResponse({ error: authError }, 401);

  const githubPat = Deno.env.get("GITHUB_PAT");
  const githubRepo = Deno.env.get("GITHUB_REPO"); // "owner/repo"
  const githubRef = Deno.env.get("GITHUB_REF") || "main";

  if (!githubPat || !githubRepo) {
    return jsonResponse({
      error: "GITHUB_PAT and/or GITHUB_REPO are not configured as Edge Function secrets. " +
        "See docs/05_DEPLOY_THE_DASHBOARD.md for how to create a scoped PAT.",
    }, 424);
  }

  try {
    const body = await req.json();
    const jobId: string = (body.job_id ?? "").trim();
    if (!jobId) return jsonResponse({ error: "job_id is required" }, 400);

    // Confirm the job actually exists and is renderable before spending a
    // GitHub Actions run on it. Uses the CALLER's own auth (via
    // requireUser's client) so this still respects RLS, not a service key.
    const authHeader = req.headers.get("Authorization") ?? "";
    const client = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: row, error: fetchError } = await client
      .from("videos").select("status").eq("job_id", jobId).single();

    if (fetchError || !row) {
      return jsonResponse({ error: `No video found with job_id=${jobId}` }, 404);
    }
    if (row.status !== "queued_for_render") {
      return jsonResponse({
        error: `Job ${jobId} has status '${row.status}', expected 'queued_for_render'. ` +
          `Nothing to render (or it's already rendering/rendered).`,
      }, 409);
    }

    const dispatchUrl = `https://api.github.com/repos/${githubRepo}/actions/workflows/render-on-demand.yml/dispatches`;
    const ghResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${githubPat}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: githubRef, inputs: { job_id: jobId } }),
    });

    if (!ghResp.ok) {
      const errText = await ghResp.text();
      return jsonResponse({
        error: `GitHub API error ${ghResp.status}: ${errText}. Check that GITHUB_PAT has ` +
          `"Actions: read and write" permission on ${githubRepo}, and that ` +
          `.github/workflows/render-on-demand.yml exists on the '${githubRef}' branch.`,
      }, 502);
    }

    // Optimistic status update so the Video Queue reflects "in progress"
    // immediately. render_existing_job() in orchestrator.py sets it back to
    // 'pending' when the render actually finishes — no webhook needed.
    await client.from("videos").update({ status: "rendering" }).eq("job_id", jobId);

    return jsonResponse({
      ok: true,
      message: "Render triggered on GitHub Actions.",
      actions_url: `https://github.com/${githubRepo}/actions/workflows/render-on-demand.yml`,
    });
  } catch (e: unknown) {
    return jsonResponse({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
