# v12 — Unread notification badges, permanent tab explanations, no Groq change

No new migration. No further changes to the Groq/backup logic this round —
see "What I'm NOT changing" below.

## What this fixes

**"Awaiting Render" confusion, made permanent, not just answered in chat.**
Both Awaiting Render and Failed tabs now show a short, always-visible
explanation directly in the app: Awaiting Render only ever fills from the
Create Video (custom prompt) page's two-step flow — adding topics or a
scheduled/manual generate run never touches it, by design.

**Unread notification badges on Failed and Published.** Per your ask: these
two tabs now show "new since you last opened this tab," not a running
lifetime total. Click the tab, the count clears; new failures or publishes
after that bring it back. Pending Review, Approved, Rendering, and Awaiting
Render keep showing plain totals on purpose — those are backlogs you need
to work through in full, not events you're being notified about.

Hover a badge to see both numbers: total and new.

**A real correctness fix underneath that:** the "new since last visit" math
depends on `updated_at` actually changing the moment a video fails or
publishes. The schema only defaults that column on INSERT — there's no
UPDATE trigger — so an existing row moving to `failed` or `published` was
silently keeping whatever timestamp it was first created with. Fixed at
every place a video's status changes to failed, publish_failed, or
published (4 call sites) so the badge reflects the real event time.

## What I'm NOT changing (on purpose, this round)

Nothing about the Groq/quota logic. Your screenshot confirms `GROQ_API_KEY`
is genuinely in GitHub secrets — but the failure shown still had the exact
OLD message text (no "was tried" language), which only exists in code
before last round's fix. That points at not having deployed v11 yet, not
at a new bug. Rather than guess further and hand you another zip on a guess,
I'm asking first: **once this is deployed, can you check whether a NEW
failure (not one from before this update) still says the OLD text, or the
new "IS configured and was tried, but it also failed: ..." text?** That
tells us definitively whether this is solved or whether something else is
actually wrong — and if it's the latter, exactly what.

## A mistake I caught before shipping, worth knowing about

While adding the tab-explanation text, an edit accidentally deleted the
`export default function VideoQueue() {` line entirely. Caught it by
re-viewing the file and running a real build before packaging, not by
assuming the edit was clean — same lesson this project keeps returning to.
Confirmed fixed: `grep` shows the line back in place, braces balance
(321/321), and `vite build` succeeds.

## Files changed

```
admin-panel/src/pages/VideoQueue.jsx   TAB_EXPLANATIONS, unread badges,
                                       localStorage last-seen tracking
engine/publish_approved.py             updated_at set explicitly (2 sites)
engine/orchestrator.py                 updated_at set explicitly (2 sites)
tools/selfcheck.py                     21 checks total (1 new)
```

## What to check on your end

1. Deploy this the usual way (unzip, commit, push — no migration).
2. Open Video Queue → Failed and Published tabs once each (clears their
   badges to a clean baseline).
3. Answer the one question above once a new failure or publish happens —
   that's what actually resolves the Groq question, not another guess from
   me.

## Verified

`python3 tools/selfcheck.py` → 21/21. Frontend builds clean. Function
declaration and brace balance double-checked directly after the JSX
edits, given the mistake caught above.
