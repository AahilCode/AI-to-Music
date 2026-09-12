# AI-to-Music — an AI-native copilot for FL Studio

> **Vision:** tell an AI what you want musically — *"dark trap beat at 145 BPM"*,
> *"make the 808 harder"*, *"fix the low end"* — and have it **actually modify
> your FL Studio project**, not just give instructions.

## How it works (the plan)

```
You → AI planner → validated JSON actions → Python engine
    → SysEx over virtual MIDI → bridge script inside FL Studio → FL Studio API
```

- The AI never touches FL Studio directly. It produces **structured actions**
  (`set_tempo`, `write_steps`, …) from a strict allowlist.
- A **validation + safety layer** checks every action; destructive ops need
  confirmation; every change is wrapped in FL Studio **undo checkpoints**.
- A tiny **bridge script** (`device_*.py`) runs inside FL Studio and executes
  commands received as MIDI SysEx — the only channel FL Studio's sandboxed
  scripting allows from the outside world.

## Status

**Phase 0 — Research: DONE.** See [`docs/phase-0-findings.md`](docs/phase-0-findings.md)
for the full feasibility report: what FL Studio can/can't do, verified against
official docs, with prior art and the proposed architecture.

**Phase 1 — Smallest possible bridge: PROPOSED, awaiting approval.**
Ping/pong → tempo read/write → transport → step-sequencer write → state snapshot.

## Roadmap

- [x] Phase 0 — Feasibility research
- [ ] Phase 1 — SysEx bridge: ping, tempo, transport, step-sequencer, snapshot
- [ ] Phase 2 — Action engine: schema, validation, executor, undo transactions
- [ ] Phase 3 — AI integration (provider-agnostic planner)
- [ ] Phase 4 — Project-state representation (read/inspect/infer)
- [ ] Phase 5 — Context-aware editing
- [ ] Phase 6 — Preview / approval / execution log UI hooks
- [ ] Phase 7 — Polished UI (chat + project state + preview)
- [ ] Phase 8 — Advanced: piano-roll notes spike, arrangement, mixing assist

## Honest limitations (known upfront)

FL Studio's scripting API **cannot**: create/delete channels, read/write
piano-roll notes, place playlist clips, or create automation clips. Each gap
has a documented workaround path — see the findings doc. We will never claim
a capability we haven't tested.
