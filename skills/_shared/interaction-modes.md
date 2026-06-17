# Interaction Modes

The pipeline supports three modes controlling how much the user is involved.
The mode decides **when** to pause. Adapted from the DLC orchestrator; the
human-approval gate is a native skill behavior, not a backend feature.

## Modes

### `interactive` — full collaboration
Pause at every decision point. Confirm the ICP criteria before classifying,
present each account's verdict + evidence and invite correction, and ask before
moving to the next stage.

### `confident` — checkpoint pauses (default)
Run autonomously between checkpoints; make reasonable calls on non-critical
choices. Always confirm the ICP criteria once up front, then classify/score the
batch and present a summary. This is the default when no mode is specified.

### `autopilot` — fully autonomous
Drive the whole batch without pausing. At each would-be checkpoint, write a
one-line self-review into the account's Decisions Log instead of asking.
**Hard-pause anyway** for irrecoverable errors (e.g. an API key that the user
intended to use is missing for the whole batch) and for genuinely ambiguous ICP
criteria that would waste work if guessed wrong.

## Resolution

1. Mode keyword in the user's prompt ("walk me through" → interactive,
   "don't ask me / handle it" → autopilot, "check in at milestones" → confident).
2. `Interaction mode` recorded in `.gtm/<slug>/state.md` (on resume).
3. Otherwise default to `confident`.

Record the resolved mode in the state file; it persists across resume unless the
user explicitly switches.

## The approval gate

The one checkpoint that matters most for GTM: **before any outreach is sent or
written** (the future `personalize` stage), pause for explicit human approval in
every mode except autopilot — and even in autopilot, surface drafted outreach for
review rather than treating "send" as autonomous. Sending messages on someone's
behalf is never a silent step.
