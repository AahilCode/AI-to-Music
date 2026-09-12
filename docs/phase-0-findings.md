# Phase 0 — Feasibility Research Findings

**Date:** 2026-09-12
**Status:** Research complete. No code written yet. Awaiting approval to begin Phase 1.
**Rule followed:** nothing below is assumed — every capability is tagged
`[DOC-VERIFIED]` (official API docs), `[PRIOR-ART]` (someone built it),
or `[MUST-TEST]` (we will prove it ourselves in Phase 1).

---

## 1. The single most important finding

FL Studio has **three separate Python scripting contexts**. They are different
programs with different powers. Confusing them is the #1 trap for beginners:

| # | Context | Since | Runs… | Can do | Cannot do |
|---|---------|-------|-------|--------|-----------|
| 1 | **MIDI Controller Scripting** (`device_*.py`) | FL 20.7 | Continuously, always-on while FL is open | Transport, tempo, mixer, channels, step sequencer, patterns, plugins, playlist-track props, undo | Piano-roll notes, channel create/delete, playlist clips, file/socket I/O |
| 2 | **Piano Roll Scripting** (`flpianoroll`) | FL 21 | Once, when user runs it from Piano Roll → Tools menu | Full note read/write (add/get/delete/clear), markers, undo-integrated | Anything outside the piano roll; cannot run in background |
| 3 | **Edison Audio Scripting** | FL 20.8.4+ | Once, inside Edison | Audio sample processing | Not relevant to us yet |

**Consequence:** our always-on "bridge into FL Studio" **must** be a
Context-1 MIDI controller script. Piano-roll note editing (Context 2) is a
separate problem we solve in a later phase.

Sources: [1](https://il-group.github.io/FL-Studio-API-Stubs/),
[2](https://flmidi-101.readthedocs.io/en/latest/scripting/fl_midi_api.html)

---

## 2. The sandbox wall (why the architecture looks the way it does)

The MIDI scripting interpreter is **sandboxed**. Reported restrictions
(`[PRIOR-ART]`, consistent with all community docs):

- ❌ No file I/O
- ❌ No sockets (no TCP/HTTP/websockets)
- ❌ No subprocess / threading / ctypes
- ❌ No importing external modules

`[MUST-TEST]` — Phase 1, Experiment 0 literally just tries `import socket`
in a script and reads the error. 30-second test, kills all doubt.

**Consequence:** the ONLY channel between an outside program and a running
FL Studio instance is **MIDI** — specifically **SysEx messages**, which can
carry arbitrary bytes. This is not our invention; it is the proven pattern:

- `OnSysEx(msg)` callback receives commands `[DOC-VERIFIED]`
- `device.midiOutSysex(bytes)` sends responses `[DOC-VERIFIED]`

So the bridge design is forced (in a good way — no decision paralysis):

```
External Python engine  ←—SysEx / virtual MIDI—→  device_*.py inside FL  ←→  FL Studio API
```

Source: [3](https://beatsage.ai/blog/fl-studio-midi-breakthrough)

---

## 3. How the outside program reaches FL Studio (virtual MIDI)

The external engine and FL Studio talk through **virtual MIDI ports**
(software cables that live inside the OS):

| OS | Option | Notes |
|----|--------|-------|
| Windows | **loopMIDI** (manual install, free for private use) | Proven by every prior-art project. Setup: ~5 min manual config |
| Windows 11 | **Windows MIDI Services loopback** (`midisrv`, CLI-created endpoints) | Zero-dependency, MIT, very new (shipped ~Feb 2026). `[MUST-TEST]` — our upgrade path, NOT the Phase 1 default |
| macOS | **IAC Driver** (built into macOS) | Free, just enable it |
| Linux | **ALSA virtual ports** | Free |

Phase 1 default: **loopMIDI on Windows / IAC on macOS** (boring, proven).
Windows MIDI Services is the stretch goal once the basics work.

Sources: [3](https://beatsage.ai/blog/fl-studio-midi-breakthrough),
[4](https://github.com/szichedelic/fl-studio-mcp),
[5](https://github.com/rosasynthesiz/flstudio-mcp)

---

## 4. Capability matrix (MIDI Controller Scripting)

### 4a. ✅ CAN — verified in official API docs

| Area | Functions (exact names from docs) | Docs |
|------|-----------------------------------|------|
| Transport | `transport.start/stop/record/isPlaying/isRecording/getLoopMode/setLoopMode/getSongPos/setSongPos/getSongLength` | [6](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/transport/) |
| Tempo read | `mixer.getCurrentTempo()` | [7](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/mixer/properties/) |
| Tempo write | `general.processRECEvent(midi.REC_Tempo, bpm*1000, midi.REC_Control \| midi.REC_UpdateControl)` | [8](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/midi/__rec_events/global%20properties/) |
| Mixer tracks | `get/setTrackVolume, get/setTrackPan, mute/solo/armTrack, get/setTrackName/Color, isTrackEnabled…` (69 fns) | [9](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/mixer/tracks/) |
| Channels | `channelCount, selectedChannel, get/setChannelName/Color, mute/soloChannel, get/setChannelVolume/Pan…` | [10](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/channels/properties/) |
| Step sequencer (per channel, active pattern) | `get/setGridBit`, `getStepParam/setStepParameterByIndex` (pitch, velocity, release, fine-pitch, pan, mod X/Y, tick-shift) | [11](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/channels/sequencer/) |
| Note trigger (play only, NOT saved) | `channels.midiNoteOn(index, note, velocity)` | [12](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/channels/notes/) |
| Patterns | `jumpToPattern` (**creates** pattern at index!), `selectPattern, clonePattern, setPatternName/Color, getPatternLength, isPatternDefault…` | [13](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/patterns/properties/) |
| Plugins (stock AND 3rd-party VST) | `plugins.isValid/getPluginName/getParamCount/getParamName/getParamValue/setParamValue…` | [14](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/plugins/) |
| Playlist tracks | `trackCount, get/setTrackName/Color, mute/solo/selectTrack…` | [15](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/playlist/tracks/) |
| Performance mode | `triggerLiveClip, getLiveBlockStatus…` (trigger existing clips, not place them) | [16](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/playlist/performance/) |
| Undo / safety | `general.saveUndo(name, flags)` (named checkpoints!), `undo/undoUp/undoDown`, full history navigation | [17](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/general/undo/) |
| Misc reads | timebase `general.getRecPPQ/getRecPPB`, dirty-flag, API version, metronome | [18](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/general/fl%20state/) |
| SysEx comms | `OnSysEx` callback in, `device.midiOutSysex` out, `device.midiOutMsg` | [19](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/device/device/) |

### 4b. ❌ CANNOT — via MIDI scripting (no function exists in official docs)

| Wanted | Status | Workaround path (later phases) |
|--------|--------|-------------------------------|
| Create / delete channels, load instruments | Not in API | Template project with pre-loaded sounds; AI programs them. Offline `.flp` editing long-term |
| Read or write piano-roll notes | Not in API (`midiNoteOn` only *plays* sound, doesn't save notes) | **Phase 1:** step-sequencer API (drums + pitched steps). **Phase 2 spike:** piano-roll scripts / native SDK plugin (BeatSage path) / offline `.flp` via `flpkit` |
| Place / move / delete playlist arrangement clips | Not in API | Performance-mode triggering now; offline `.flp` later |
| Create automation clips | Not in API (live values only) | Set live values now; offline `.flp` later |
| Read audio / waveforms | Not in API | Render + analyze audio files (Phase 8) |
| Sockets, files, threads in script | Sandbox forbids | SysEx protocol (this is the whole design) |

### 4c. Piano Roll Scripting (Context 2) — verified, but manually triggered

`flpianoroll.score`: `addNote/getNote/deleteNote/clearNotes`,
`addMarker/getMarker/deleteMarker`, note count, PPQ, time signature.
Full CRUD + undo support — but scripts run **one-shot from the Tools menu**.
How (or whether) an external program can trigger them is an open
`[MUST-TEST]` question for the Phase 2 spike — not Phase 1.

Source: [20](https://il-group.github.io/FL-Studio-API-Stubs/piano_roll_scripting/flpianoroll/score/)

---

## 5. Prior art (all confirm the architecture — and the gaps)

| Project | What it proves | License |
|---------|----------------|---------|
| [szichedelic/fl-studio-mcp](https://github.com/szichedelic/fl-studio-mcp) | MCP server (Node) + `device_FLBridge.py`, SysEx over loopMIDI/IAC. Transport, channels, patterns | MIT |
| [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp) | Python, 67 tools, mixing-focused, **preview + log + reversible** changes, real level measurement | MIT |
| [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) | MCP + MIDI + piano-roll scripts hybrid; any MCP client (Claude/Cursor/…) | MIT |
| [BeatSage blog](https://beatsage.ai/blog/fl-studio-midi-breakthrough) | Documents 6 dead ends: internal SysEx bridge ❌, teVirtualMIDI ❌, rtmidi virtual ports on Win ❌, Win MIDI Services ✅ (new), cross-channel note write via native SDK flag ✅ (C++, advanced) | Commercial |
| [flpkit (PyPI)](https://pypi.org/project/flpkit/) | Offline `.flp` read/write, differential-tested vs 164 projects, **live-verified with FL Studio 2026**. Successor path to abandoned GPL `PyFLP` | Open |

**Our differentiation (to earn the portfolio claim):** provider-agnostic
action engine with validation + transactions + project-state snapshots,
built incrementally and documented as a learning project — not a thin
MCP wrapper. MCP compatibility can be a *bonus interface* later.

---

## 6. Recommended architecture

```
User
 ↓  (Phase 1: CLI test scripts → later: chat UI and/or MCP server)
AI Planner (provider-agnostic: Muse / GPT / Gemini / local)
 ↓  JSON actions ONLY (strict schema, allowlist — model can't invent ops)
Validator + Safety (bounds, destructive-confirm, op limits, undo checkpoints)
 ↓
Python engine  ←→  virtual MIDI (loopMIDI / IAC / ALSA)
   SysEx protocol: request IDs, chunking, timeouts, retries
 ↓
device_aicopilot.py (inside FL Studio)  ←→  FL Studio API
```

Why this shape:
1. The sandbox **forces** SysEx-over-MIDI (Section 2) — no alternative.
2. Prior art **validates** it 4+ times over (Section 5).
3. JSON-action layer keeps AI swappable and testable **without FL Studio**.
4. `saveUndo` checkpoints give us transactions almost for free.

---

## 7. Proposed Phase 1 — smallest proofs, in order

Each experiment is one tiny vertical slice with a pass/fail test.
**Nothing proceeds until the previous experiment passes.**

| # | Experiment | What it proves | Success looks like |
|---|-----------|----------------|-------------------|
| 0 | `import socket` in a script; read Script Output window | Sandbox reality (kills assumptions) | Visible error confirming no sockets |
| 1 | SysEx **ping/pong**: external Python → FL → reply | The comms channel (riskiest assumption in the project) | `pong` response < 100ms, 100/100 messages |
| 2 | `get_tempo` / `set_tempo` (145 BPM) | Read + write of project state | FL tempo display changes; read-back matches |
| 3 | `play` / `stop` / `is_playing` | Transport control | Audible start/stop on command |
| 4 | Read step-grid of channel 0; write 4-on-floor kick | Real musical modification end-to-end | Kick pattern appears in Channel Rack, plays correctly |
| 5 | Full snapshot: tempo + channels + patterns + mixer → JSON | State inspection the AI will need | Complete JSON dump of a demo project |

**Out of scope for Phase 1:** AI/LLM, piano-roll notes, arrangement clips,
channel create/delete, UI, automation. All explicitly deferred with reasons
in Section 4b.

**How we work (sandbox reality):** this dev environment has no FL Studio,
so FL-side tests run on **your** machine. I will structure code so that
everything except the thin MIDI transport is unit-testable here, and every
FL-side test will be a single copy-paste command with exact expected output.

---

## 8. Honest resume-check (will update as we build)

After Phase 1 we can truthfully claim: *"Built a bidirectional Python↔FL
Studio bridge (SysEx-over-virtual-MIDI protocol) proving programmatic
control of transport, tempo, step-sequencer patterns, mixer and plugin
parameters."* The full "copilot" claim waits until Phases 2–4 actually work.

---

## 9. Sources

1. Official API stubs/docs — https://il-group.github.io/FL-Studio-API-Stubs/
2. FL MIDI Scripting 101 — https://flmidi-101.readthedocs.io/
3. BeatSage: How We Got AI Into FL Studio — https://beatsage.ai/blog/fl-studio-midi-breakthrough
4. szichedelic/fl-studio-mcp — https://github.com/szichedelic/fl-studio-mcp
5. rosasynthesiz/flstudio-mcp — https://github.com/rosasynthesiz/flstudio-mcp
6–19. Individual API module pages (linked inline in Section 4a).
20. Piano roll Score API — https://il-group.github.io/FL-Studio-API-Stubs/piano_roll_scripting/flpianoroll/score/
