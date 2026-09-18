"""Web Server for the AI-to-Music Copilot Web UI with Session Memory."""

import os
import time
from flask import Flask, render_template, request, jsonify

from . import transport
from . import actions
from . import ai

app = Flask(__name__)

# In-memory session chat history
CHAT_HISTORY = []


def _get_bridge():
    """Open a bridge connection with default Copilot CMD ports."""
    return transport.open_ports("Copilot CMD", "Copilot CMD")


@app.route("/")
def index():
    """Render the dashboard UI."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    """Return current BPM and channels from FL Studio."""
    try:
        bridge = _get_bridge()
        try:
            tempo = bridge.request("get_tempo")
            ch_raw = bridge.request("get_channels")
            ch_list = [c.strip() for c in ch_raw.split(",") if c.strip()]
            return jsonify({
                "ok": True,
                "tempo": tempo,
                "channels": ch_list
            })
        finally:
            bridge.close()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/transport", methods=["POST"])
def api_transport():
    """Execute transport controls (play, stop)."""
    data = request.json or {}
    action = data.get("action", "play")
    try:
        bridge = _get_bridge()
        try:
            if action == "play":
                bridge.request("play")
            elif action == "stop":
                bridge.request("stop")
            return jsonify({"ok": True})
        finally:
            bridge.close()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/clear_memory", methods=["POST"])
def api_clear_memory():
    """Reset the conversation memory."""
    global CHAT_HISTORY
    CHAT_HISTORY = []
    return jsonify({"ok": True, "message": "Conversation memory cleared!"})


@app.route("/api/prompt", methods=["POST"])
def api_prompt():
    """Process natural language music generation prompt with chat memory."""
    global CHAT_HISTORY
    data = request.json or {}
    user_prompt = data.get("prompt", "")
    if not user_prompt:
        return jsonify({"ok": False, "error": "Empty prompt"}), 400

    start_time = time.monotonic()
    try:
        bridge = _get_bridge()
        try:
            # 1. Read current DAW state
            tempo_payload = bridge.request("get_tempo")
            current_tempo = float(tempo_payload)
            channels_payload = bridge.request("get_channels")
            available_channels = [c.strip() for c in channels_payload.split(",") if c.strip()]

            # 2. Plan actions with AI (passing ongoing CHAT_HISTORY)
            plan, raw_json_reply = ai.generate_action_plan(
                user_prompt, available_channels, current_tempo, chat_history=CHAT_HISTORY
            )

            # 3. Execute actions batch
            results = actions.execute_batch(plan, bridge)
            duration = time.monotonic() - start_time

            # Format human-readable summary
            summary = []
            for act, res in results:
                act_type = act.get("type")
                if act_type == "set_tempo":
                    summary.append(f"Set tempo to {act.get('bpm')} BPM")
                elif act_type == "set_step_pattern":
                    summary.append(f"Wrote 4-bar drum groove to '{act.get('channel')}' (steps: {act.get('steps')})")
                elif act_type == "play_layered_progression":
                    summary.append("Recorded Transcendent Multi-Layered Melodic Progression ✨🎹")
                elif act_type == "record":
                    summary.append("Armed live recording in FL Studio ⏺")
                elif act_type == "play":
                    summary.append("Started playback ▶")
                elif act_type == "stop":
                    summary.append("Stopped playback ⏹")
                elif act_type == "clear_channel":
                    summary.append(f"Cleared channel '{act.get('channel')}'")
                else:
                    summary.append(f"Executed {act_type}")

            # Save this turn to conversation memory!
            CHAT_HISTORY.append({"role": "user", "content": user_prompt})
            CHAT_HISTORY.append({"role": "assistant", "content": raw_json_reply})

            # Keep memory lean (last 10 turns max)
            if len(CHAT_HISTORY) > 10:
                CHAT_HISTORY = CHAT_HISTORY[-10:]

            return jsonify({
                "ok": True,
                "duration": duration,
                "results": summary
            })
        finally:
            bridge.close()

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def run():
    print("\n" + "=" * 55)
    print("🚀 AI-to-Music Copilot Web Server Started (Memory Enabled)!")
    print("👉 Open your browser at: http://localhost:5001")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    run()
