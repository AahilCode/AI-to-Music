# Phase 1 — Smallest Possible FL Studio Bridge

**Goal:** prove our own code can talk to FL Studio and change something real.
**Method:** 6 tiny experiments. Each has a pass/fail test. Nothing proceeds
until the previous experiment passes.

**Your machine (from your answers):** macOS + FL Studio + Python 3.10+.
This doc is written for that setup.

---

## Part A — One-time macOS setup (~15 min, do once)

### A1. Create two virtual MIDI buses (the "cables")

Our engine and FL Studio talk through two one-way software MIDI cables:

- `Copilot CMD` — engine → FL Studio (commands)
- `Copilot RSP` — FL Studio → engine (responses)

Steps:

1. Open **Audio MIDI Setup** (in /Applications/Utilities).
2. Menu: **Window → Show MIDI Studio**.
3. Double-click **IAC Driver** → check **"Device is online"**.
4. Click **+** twice to add two ports. Double-click each to rename:
   `Copilot CMD` and `Copilot RSP`.

Why two instead of one? One cable per direction means commands and responses
can never get mixed up or echo back to the sender. Debugging is 10× easier.

### A2. Install the bridge script into FL Studio

1. Copy `fl_bridge/device_aicopilot.py` from this repo into:

   ```
   ~/Documents/Image-Line/FL Studio/Settings/Hardware/AICopilot/device_aicopilot.py
   ```

   (Create the `AICopilot` folder if it doesn't exist. The filename MUST
   start with `device_` or FL Studio ignores it.)
2. Restart FL Studio (or rescan MIDI scripts).
3. Verify: **Options → MIDI Settings → Input** → click an input device →
   the **Controller type** dropdown should list **"AI Copilot Bridge"**.

### A3. Wire FL Studio's MIDI settings

In **Options → MIDI Settings**:

| Section | Device | Enable | Controller type / Port |
|---------|--------|--------|------------------------|
| Input | `Copilot CMD` | ✅ Enable | Controller type = **AI Copilot Bridge**, Port = **10** |
| Output | `Copilot RSP` | ✅ Enable | Port = **10** (same number links output to our script) |

Leave "Send master sync" OFF.

### A4. Open the Script Output window (our "console")

In FL Studio menu: **View → Script output**. Everything our bridge script
`print()`s appears here, including errors. Keep it open during all tests —
when something fails, this window tells us why.

### A5. Install the engine's MIDI library (on your Mac)

```bash
cd engine
pip install -r requirements.txt   # mido + python-rtmidi (talks to macOS CoreMIDI)
```

Check macOS sees the buses:

```bash
python -m copilot.cli list-ports
```

You should see `Copilot CMD` and `Copilot RSP` in the output.

---

## Part B — Experiment cards

### Experiment 0 — Sandbox probe (kill assumptions, 2 min)

**Question:** what is our FL-side script actually allowed to do?
**Run:** with the script installed + selected (A2–A3), FL Studio prints the
probe automatically on load. Look at **Script output**.
**Expect:** something like:

```
[AICopilot] bridge v0.1 init
[AICopilot] API version: 37
[AICopilot] device: Copilot CMD / port 10 / output assigned: True
[AICopilot] import json: OK|FAIL ...
[AICopilot] import socket: OK|FAIL ...
```

**Pass:** we learn the truth about `json`/`socket`/etc. Copy the whole block
and send it back — it decides our protocol design in Phase 2.
**Fail looks like:** script doesn't appear in Controller type (wrong folder /
filename), or `output assigned: False` (output port mismatch — recheck A3).

### Experiment 1 — SysEx ping/pong (the riskiest assumption)

**Question:** can an external Python program send a command to FL Studio and
get a reply?
**Run (Mac terminal):**

```bash
cd engine
python -m copilot.cli ping
```

**Expect:**

```
PONG from FL Studio in 12.3 ms (req #1)
```

**Pass:** reply arrives, round-trip < 100 ms, 20/20 pings succeed
(`... ping --count 20`).
**Fail looks like:** `TimeoutError` (ports wrong / script not selected /
wrong Controller type) — the CLI prints which ports it opened to help debug.

### Experiment 2 — Tempo read/write (coming next)

`get_tempo` / `set_tempo 145` — FL's tempo display changes; read-back matches.
Proves we can read AND write project state. (Bridge v0.2 + CLI update.)

### Experiment 3 — Transport (after Exp 2)

`play` / `stop` / `is_playing` — audible start/stop on command.

### Experiment 4 — Step-sequencer write (after Exp 3)

Read channel 0's grid, write a 4-on-floor kick to the active pattern.
First real musical modification, end to end.

### Experiment 5 — State snapshot (after Exp 4)

Dump tempo + channels + patterns + mixer as JSON — the foundation the AI
will later read before making decisions.

---

## Rules for this phase

1. One experiment at a time. No AI, no UI, no piano-roll notes yet.
2. Every FL-side test is a single copy-paste command with exact expected output.
3. All failures get debugged from the **actual error** (Script output window
   + CLI output), not by rewriting everything.
4. Everything except the thin MIDI transport must be unit-testable without
   FL Studio (`cd engine && python -m unittest discover -s tests -t .`).
