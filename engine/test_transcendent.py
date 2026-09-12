"""Test script: Play a Transcendent, Multi-Layered Ascending Melody & Chord Progression."""

import time
import random
import mido

outport = mido.open_output("IAC Driver Copilot CMD")
print("✨ Connected! Playing Transcendent Ascending Melody (Cmin9 -> AbMaj9 -> EbMaj9 -> Gmin7)...")

# 4 Transcendent Chords with Deep Bass + Lush Mid Voicings + Soaring Ascending Top Line
SECTIONS = [
    {
        "name": "Bar 1: C Minor 9 (Dark / Space)",
        "bass": [24, 36],              # Deep C1 & C2 sub bass
        "pad": [48, 55, 58, 62, 63],   # Lush Cmin9 chord
        "lead": [
            (60, 0.4, 75),             # C4 (warm entry)
            (63, 0.3, 80),             # Eb4
            (67, 0.3, 85),             # G4
            (70, 0.25, 90),            # Bb4 (ascending)
            (74, 0.25, 95),            # D5
            (75, 0.8, 105),            # High Eb5 (SOARING PEAK - held long)
        ]
    },
    {
        "name": "Bar 2: Ab Major 9 (Emotional / Floating)",
        "bass": [20, 32],              # Ab0 & Ab1
        "pad": [44, 51, 56, 60, 63],   # AbMaj9
        "lead": [
            (72, 0.4, 85),             # C5
            (70, 0.3, 80),             # Bb4
            (68, 0.3, 85),             # Ab4
            (72, 0.25, 90),            # C5
            (75, 0.25, 95),            # Eb5
            (79, 0.8, 110),            # High G5 (SOARING HEAVENLY PEAK)
        ]
    },
    {
        "name": "Bar 3: Eb Major 9 (Uplifting / Cinematic)",
        "bass": [27, 39],              # Eb1 & Eb2
        "pad": [46, 51, 58, 62, 65],   # EbMaj9
        "lead": [
            (67, 0.35, 80),            # G4
            (70, 0.3, 85),             # Bb4
            (74, 0.25, 90),            # D5
            (75, 0.25, 95),            # Eb5
            (79, 0.3, 100),            # G5
            (82, 0.85, 112),           # Ultra High Bb5 (Apex of the entire song)
        ]
    },
    {
        "name": "Bar 4: G Minor 7 (Tension / Resolution)",
        "bass": [22, 34],              # G0 & G1
        "pad": [43, 50, 55, 58, 62],   # Gmin7
        "lead": [
            (82, 0.3, 95),             # Bb5 (graceful descent)
            (79, 0.3, 90),             # G5
            (74, 0.3, 85),             # D5
            (70, 0.4, 80),             # Bb4
            (67, 1.0, 75),             # G4 (soft emotional resolution)
        ]
    }
]

def play_layer(section):
    print(f"  ▶ {section['name']}")
    
    # 1. Hit Deep Bass & Lush Pad together and HOLD them
    for note in section["bass"] + section["pad"]:
        vel = max(40, min(115, 80 + random.randint(-4, 4)))
        outport.send(mido.Message('note_on', note=note, velocity=vel))
        
    # 2. Play the soaring melodic notes with dynamic breathing timing
    for note, duration, velocity in section["lead"]:
        vel = max(40, min(125, velocity + random.randint(-4, 4)))
        outport.send(mido.Message('note_on', note=note, velocity=vel))
        time.sleep(duration * 0.85)
        outport.send(mido.Message('note_off', note=note, velocity=0))
        time.sleep(duration * 0.15)
        
    # 3. Release Bass and Pad at the end of the bar
    for note in section["bass"] + section["pad"]:
        outport.send(mido.Message('note_off', note=note, velocity=0))
    time.sleep(0.08)

# Play the 4-bar progression twice!
for loop in range(2):
    print(f"\n--- Ascension Loop {loop + 1}/2 ---")
    for sec in SECTIONS:
        play_layer(sec)

print("\n✨ Done playing transcendent progression!")
outport.close()
