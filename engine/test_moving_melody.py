"""Play a moving, humanized piano arpeggio & bassline over drums in FL Studio."""

import time
import random
import mido

# Open MIDI output
outport = mido.open_output("IAC Driver Copilot CMD")

print("🎹 Playing a moving, dynamic Piano Arpeggio & Bassline...")

# Chord definitions with root bass notes and melody arpeggios
PROGRESSION = [
    {
        "name": "C Minor (Dark)",
        "bass": 36, # Deep C2 bass
        "arp": [48, 60, 63, 67, 72, 67, 63, 60] # C3, C4, Eb4, G4, C5...
    },
    {
        "name": "Ab Major (Emotional)",
        "bass": 32, # Ab1
        "arp": [44, 56, 60, 63, 68, 63, 60, 56] # Ab, C, Eb...
    },
    {
        "name": "Eb Major (Uplifting)",
        "bass": 39, # Eb2
        "arp": [46, 58, 63, 67, 70, 67, 63, 58]
    },
    {
        "name": "Bb Major (Resolution)",
        "bass": 34, # Bb1
        "arp": [46, 58, 62, 65, 70, 65, 62, 58]
    }
]

def play_note(note, duration, velocity=80):
    # Add slight human random velocity variation
    vel = max(40, min(120, velocity + random.randint(-8, 8)))
    outport.send(mido.Message('note_on', note=note, velocity=vel))
    time.sleep(duration * 0.9)
    outport.send(mido.Message('note_off', note=note, velocity=0))
    time.sleep(duration * 0.1)

# Start playback in FL Studio so the drums play in the background
outport.send(mido.Message('start'))
time.sleep(0.1)

try:
    for loop in range(2):
        print(f"\n--- Section Loop {loop + 1}/2 ---")
        for chord in PROGRESSION:
            print(f"  ▶ Chord: {chord['name']}")
            
            # Hit the deep bass note first
            outport.send(mido.Message('note_on', note=chord["bass"], velocity=95))
            
            # Play the 8-note flowing arpeggio
            for note in chord["arp"]:
                play_note(note, duration=0.18, velocity=75)
                
            # Release bass note
            outport.send(mido.Message('note_off', note=chord["bass"], velocity=0))

finally:
    # Stop playback when done
    outport.send(mido.Message('stop'))
    outport.close()
    print("\n✨ Finished playing!")
