# v10 — The "Customize" option was too easy to miss

No new migration, no backend changes.

## The two questions this answers

**"Does Add Topics put anything in Awaiting Render?"** No — never. Add
Topics only writes rows into Topic Studio; it never touches the video
queue at all. Awaiting Render is only ever used by the Create Video
(custom prompt) page's two-step flow. Check Topic Studio for new topics,
not the queue.

**"Clicking Add Topics doesn't ask anything, it just runs."** That part of
the behavior is correct — the main button is a deliberate one-click action
(all channels, no confirmation), matching the "press and it just does the
thing" design from earlier in this project. What was actually missing: a
way to choose a channel and count *does* exist, but it was styled as
near-invisible muted text sitting under the button — easy to press the
button without ever noticing there was more.

## The fix

The "Customize" toggle is now a real, bordered, full-width button of its
own — impossible to mistake for plain text. Screenshotted before shipping
this time, given the exact class of mistake (styling so subtle it reads as
broken) has happened once already in this project.

## Files changed

```
admin-panel/src/components/ManualControls.jsx   Customize toggle restyled
```

## Verified

`python3 tools/selfcheck.py` → 18/18. Rendered and screenshotted the actual
button before packaging.
