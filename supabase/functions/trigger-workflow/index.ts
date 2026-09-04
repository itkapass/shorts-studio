// trigger-workflow/index.ts
//
// Lets the dashboard's manual buttons ("Add Topics Now", "Generate Video
// Now", "Publish Now") start a GitHub Actions run, instead of you having to
// leave the dashboard, open the Actions tab, find the right workflow and
// press Run workflow.
//
// This is a generalised version of trigger-render, which could only ever
// dispatch one specific workflow. Same security model:
//
//   - The GitHub token is a real credential, so it lives as an Edge Function
//     secret and never reaches the browser.
//   - The caller must be a logged-in dashboard user (requireUser).
//   - ALLOWED is a hardcoded allow-list. A caller cannot name an arbitrary
//     workflow file, even a real one in your repo. Passing the workflow name
//     straight through to the GitHub API would mean anyone who could log in
//     could run anything in .github/workflows — including, one day, a
//     workflow you add later that does something destructive.
//
// Deploy:  supabase functions deploy trigger-workflow
// Secrets: supabase secrets set GITHUB_PAT=github_pat_...
//          supabase secrets set GITHUB_REPO=itkapass/shorts-studio
//          supabase secrets set GITHUB_REF=main
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { requireUser, jsonResponse, CORS_HEADERS } from "../_shared/auth.ts";

// Short friendly name -> real workflow filename.
const ALLOWED: Record<string, string> = {
  topics: "add-topics.yml",
  generate: "generate.yml",
  publish: "publish.yml",
  health: "health-check.yml",
  cleanup: "cleanup.yml",
  trending: "discover-trending.yml",
  alerts: "test-alerts.yml",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });

  const { user, error: authError } = await requireUser(req);
  if (!user) return jsonResponse({ error: authError }, 401);

  const githubPat = Deno.env.get("GITHUB_PAT");
  const githubRepo = Deno.env.get("GITHUB_REPO");
  const githubRef = Deno.env.get("GITHUB_REF") || "main";

  if (!githubPat || !githubRepo) {
    return jsonResponse({
      error:
        "GITHUB_PAT and/or GITHUB_REPO are not set as Edge Function secrets. " +
        "The manual buttons need them. See docs/11_SCHEDULING_AND_MANUAL_CONTROLS.md.",
    }, 424);
  }

  try {
    const body = await req.json();
    const which: string = (body.workflow ?? "").trim();
    const inputs: Record<string, string> = body.inputs ?? {};
    const jobId: string = (body.job_id ?? "").trim();

    const file = ALLOWED[which];
    if (!file) {
      return jsonResponse({
        error: `Unknown workflow '${which}'. Allowed: ${Object.keys(ALLOWED).join(", ")}`,
      }, 400);
    }

    const authHeader = req.headers.get("Authorization") ?? "";
    const client = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: authHeader } } },
    );

    // "Publish Now" is two actions, not one: flag THIS video as a queue
    // jumper, then wake the publish job. Flagging without triggering would
    // mean waiting up to an hour for the next cron; triggering without
    // flagging would just publish whatever was next in line instead of the
    // video you actually pressed the button on.
    if (which === "publish" && jobId) {
      const { error: flagError } = await client
        .from("videos")
        .update({ publish_now: true })
        .eq("job_id", jobId)
        .eq("status", "approved");
      if (flagError) {
        return jsonResponse({
          error:
            `Could not mark ${jobId} for immediate publishing: ${flagError.message}. ` +
            `Note that only APPROVED videos can be published — approve it first.`,
        }, 409);
      }
    }

    const dispatchUrl =
      `https://api.github.com/repos/${githubRepo}/actions/workflows/${file}/dispatches`;
    const ghResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${githubPat}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: githubRef, inputs }),
    });

    if (!ghResp.ok) {
      const errText = await ghResp.text();
      return jsonResponse({
        error:
          `GitHub API error ${ghResp.status}: ${errText}. Check that GITHUB_PAT has ` +
          `"Actions: read and write" on ${githubRepo}, and that ` +
          `.github/workflows/${file} exists on the '${githubRef}' branch.`,
      }, 502);
    }

    return jsonResponse({
      ok: true,
      message: `Started '${which}' on GitHub Actions.`,
      actions_url: `https://github.com/${githubRepo}/actions/workflows/${file}`,
    });
  } catch (e: unknown) {
    return jsonResponse({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
