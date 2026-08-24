// generate-storyboard/index.ts
//
// Backs the Admin Panel's "Create Video" page. THIS REPLACES A MOCK: the
// previous version of that page did simple string-matching on the prompt
// ("if promptLower.includes('titan')") and filled in one hardcoded template
// — every generated "storyboard" had the same fixed scenes 2-4, the same
// b-roll keywords, and a hardcoded "$22-$28 CPM" estimate, regardless of
// what you actually typed. Nothing called an LLM at all.
//
// The browser can't safely call Gemini directly (that would mean shipping
// the Gemini API key in the public JS bundle). This function is the fix:
// it holds the key server-side (as an Edge Function secret, never exposed
// to the client) and does the real generation, mirroring the same prompt
// design as engine/script_generator.py so a video generated from the
// dashboard gets genuinely comparable quality to one generated from the
// scheduled pipeline.
//
// Deploy: supabase functions deploy generate-storyboard
// Secret:  supabase secrets set GEMINI_API_KEY=...   (and optionally GEMINI_MODEL)
import { requireUser, jsonResponse, CORS_HEADERS } from "../_shared/auth.ts";
import { ICON_NAMES } from "../_shared/icons.ts";

const DEFAULT_MODEL = "gemini-3.5-flash"; // keep in sync with engine/script_generator.py

function buildSystemPrompt(renderStyle: string, numScenes: number): string {
  let visualField: string;
  let visualRule: string;

  if (renderStyle === "whiteboard_sketch") {
    visualField = `"icons": ["1 to 3 icon names from this exact list — nothing else: ${ICON_NAMES.join(", ")}"]`;
    visualRule = "5. VISUALS: this is a hand-drawn whiteboard-explainer video. Each scene shows 1-3 simple " +
      "line icons drawn from the fixed vocabulary provided — pick the ones that best represent the scene's idea. " +
      "Do not invent icon names.";
  } else if (renderStyle === "quote_card") {
    visualField = "";
    visualRule = "5. VISUALS: this is a minimal text-only quote-card video (no footage, no icons) — the words " +
      "themselves have to carry all the weight. Write with that in mind: vivid, quotable, rhythmic language.";
  } else {
    visualField = '"visual_keyword": "Specific stock footage search phrase (e.g. \'silicon wafer cleanroom glow\', ' +
      "'server room blue light corridor')\"";
    visualRule = "5. VISUALS: provide a specific, concrete stock-footage search phrase per scene — specific " +
      "enough that a real b-roll clip will visually match the sentence being spoken.";
  }

  const sceneFields = [
    '"scene_number": 1',
    '"voice_text": "The exact words spoken in this scene."',
    visualField,
    '"visual_mood": "dark|bright|neutral|dramatic"',
    '"sfx": "none|whoosh|digital_pop|riser|glitch|impact"',
    '"transition": "cut|fade|zoom_in|zoom_out"',
  ].filter(Boolean).join(",\n      ");

  return `
You are an experienced short-form video scriptwriter for YouTube Shorts. Your
goal is genuine viewer retention: specific, well-earned writing that rewards
someone for watching to the end — not filler, and not hollow engagement bait.

RULES:
1. TOTAL NARRATION: 40-50 seconds read aloud (roughly 110-140 spoken words
   total across all ${numScenes} scenes).
2. SCENE 1 (THE HOOK - first 3 seconds): a genuinely surprising, specific
   fact or question related to the topic. Never "Hello guys" or "In this
   video". The hook has to be TRUE and be something the rest of the video
   actually delivers on — don't promise a twist you don't pay off.
3. PACING: every scene is punchy (1-2 sentences max). Cut every unnecessary word.
4. ENDING (scene ${numScenes}): end with a clear, honest reason to keep
   engaging — a specific follow-up question, what part 2 will cover, or why
   subscribing matters for THIS channel. Do not use empty engagement-bait
   instructions like "comment X and I'll DM you" — YouTube's spam policies
   discourage this, and it reads as hollow to viewers anyway.
${visualRule}
6. Do not state invented statistics or claims about real, named companies or
   people as fact unless they're well-established public knowledge.

OUTPUT FORMAT (strict JSON, no extra markdown or commentary):
{
  "video_title": "Clear, specific, honest title (under 65 chars, include #Shorts)",
  "description": "1-2 sentence description with relevant keywords",
  "hashtags": ["#Shorts", "...9 more specific, relevant tags"],
  "hook_concept": "Brief explanation of why scene 1 hooks the viewer",
  "scenes": [
    {
      ${sceneFields}
    }
  ]
}`.trim();
}

async function callGemini(systemPrompt: string, userPrompt: string) {
  const apiKey = Deno.env.get("GEMINI_API_KEY");
  if (!apiKey) throw new Error("GEMINI_API_KEY not configured as an Edge Function secret.");
  const model = Deno.env.get("GEMINI_MODEL") || DEFAULT_MODEL;

  const resp = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: userPrompt }] }],
        systemInstruction: { parts: [{ text: systemPrompt }] },
        generationConfig: { temperature: 0.9, topP: 0.95, responseMimeType: "application/json" },
      }),
    },
  );

  if (!resp.ok) {
    const body = await resp.text();
    if (resp.status === 404 || body.toLowerCase().includes("not found")) {
      throw new Error(
        `Gemini model '${model}' not found (${resp.status}). It's likely been deprecated — set the ` +
        `GEMINI_MODEL secret to a current model from https://ai.google.dev/gemini-api/docs/models. Raw: ${body}`,
      );
    }
    throw new Error(`Gemini API error ${resp.status}: ${body}`);
  }

  const data = await resp.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error(`Gemini returned no text. Raw response: ${JSON.stringify(data).slice(0, 500)}`);
  return text;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });

  const { user, error: authError } = await requireUser(req);
  if (!user) return jsonResponse({ error: authError }, 401);

  try {
    const body = await req.json();
    const prompt: string = (body.prompt ?? "").trim();
    const toneName: string = body.tone_name ?? "Curious Explainer";
    const toneDesc: string = body.tone_desc ?? "Clear, specific, genuinely informative";
    const hookStyle: string = body.hook_style ?? "Surprising Fact / Question";
    const numScenes: number = body.num_scenes ?? 5;
    const renderStyle: string = ["stock_footage", "whiteboard_sketch", "quote_card"].includes(body.render_style)
      ? body.render_style
      : "stock_footage";

    if (!prompt) return jsonResponse({ error: "prompt is required" }, 400);

    const systemPrompt = buildSystemPrompt(renderStyle, numScenes);
    const userPrompt = `SUBJECT:\n${prompt}\n\nSTYLE & TONE:\n${toneName} — ${toneDesc}\n\n` +
      `HOOK REQUIREMENT (Scene 1):\n${hookStyle}\n\nNUMBER OF SCENES: ${numScenes}\n\n` +
      `Generate a ${numScenes}-scene storyboard adhering strictly to the JSON schema.`;

    const raw = await callGemini(systemPrompt, userPrompt);
    const cleaned = raw.trim().replace(/^```json\s*/i, "").replace(/\s*```$/, "");

    let storyboard;
    try {
      storyboard = JSON.parse(cleaned);
    } catch {
      return jsonResponse({ error: "Gemini returned invalid JSON", raw: raw.slice(0, 500) }, 502);
    }

    for (const key of ["video_title", "description", "hashtags", "scenes"]) {
      if (!(key in storyboard)) return jsonResponse({ error: `Storyboard missing required key: ${key}` }, 502);
    }

    for (const [i, scene] of storyboard.scenes.entries()) {
      if (!scene.voice_text || !String(scene.voice_text).trim()) {
        return jsonResponse({ error: `Scene ${i + 1} has no voice_text — refusing to return a mute scene.` }, 502);
      }
      scene.transition ??= "cut";
      scene.sfx ??= "none";
      scene.visual_mood ??= "neutral";
      if (renderStyle === "whiteboard_sketch") {
        const icons = (scene.icons ?? []).filter((ic: string) => ICON_NAMES.includes(ic));
        scene.icons = icons.length ? icons : ["lightbulb"];
      } else if (renderStyle === "stock_footage" && !scene.visual_keyword?.trim()) {
        scene.visual_keyword = `${scene.visual_mood} abstract technology background`;
      }
    }

    if (!storyboard.hashtags.includes("#Shorts")) storyboard.hashtags.unshift("#Shorts");
    if (!storyboard.video_title.includes("#Shorts")) storyboard.video_title += " #Shorts";

    return jsonResponse({ storyboard, render_style: renderStyle });
  } catch (e: unknown) {
    return jsonResponse({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
