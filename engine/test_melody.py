"""Test script: Play a Dark Emotional Chord Progression on Piano/Guitar in FL Studio."""

import time
import mido

# Open output port to FL Studio
outport = mido.open_output("IAC Driver Copilot CMD")

print("🎹 Connected! Playing Dark Emotional Piano Chords to FL Studio...")

# Note Numbers (MIDI standard):
# 60 = Middle C (C4), 63 = D#4/Eb4, 67 = G4, etc.

CHORDS = [
    # Chord 1: C Minor (Dark / Sad)
    {"name": "C Minor", "notes": [48, 60, 63, 67], "duration": 1.2},
    # Chord 2: Ab Major (Emotional)
    {"name": "Ab Major", "notes": [44, 56, 60, 63, 68], "duration": 1.2},
    # Chord 3: Eb Major (Uplifting)
    {"name": "Eb Major", "notes": [46, 58, 63, 67], "duration": 1.2},
    # Chord 4: Bb Major / G Minor (Resolution)
    {"name": "Bb Major", "notes": [46, 58, 62, 65], "duration": 1.2},
]

def play_chord(notes, duration, velocity=85):
    # Press all keys together
    for n in notes:
        outport.send(mido.Message('note_on', note=n, velocity=velocity))
    
    time.sleep(duration)
    
    # Release all keys
    for n in notes:
        outport.send(mido.Message('note_off', note=n, velocity=0))
    time.sleep(0.05)

# Play the 4-chord progression twice!
for loop in range(2):
    print(f"\n--- Playing Progression (Loop {loop + 1}/2) ---")
    for chord in CHORDS:
        print(f"  ▶ Playing: {chord['name']} ({chord['notes']})")
        play_chord(chord["notes"], chord["duration"])

print("\n✨ Done! Beautiful piano chords played.")
outport.close()
