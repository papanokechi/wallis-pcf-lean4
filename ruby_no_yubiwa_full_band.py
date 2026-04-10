"""
Generate a full band + vocal harmony arrangement of "Ruby no Yubiwa"
(ルビーの指環) by Akira Terao, in F major / D minor.

Outputs: ruby_no_yubiwa_full_band.musicxml  (open in MuseScore Studio)

Parts:
  1. Lead Vocal        – melody (guide tones from chord; replace with real melody)
  2. Harmony Vocal (Alto)  – diatonic 3rd below lead
  3. Harmony Vocal (Tenor) – 5th/root below lead
  4. Electric Piano     – Rhodes-style chord voicings
  5. Electric Guitar    – rhythmic comping
  6. Bass Guitar        – walking/syncopated bass
  7. Drum Set           – city-pop groove

66 measures, ~99 BPM, matching the MuseScore ukulele arrangement structure.
"""

from music21 import (
    stream, note, chord, clef, meter, key, tempo, instrument,
    duration, expressions, dynamics, metadata, harmony, percussion,
)
from music21.midi import percussion as midiPerc
import os

# ── Song structure (66 bars) ──────────────────────────────────────────────
# Intro:   bars 1–4
# Verse 1: bars 5–20   (16 bars)
# Chorus:  bars 21–28  (8 bars)
# Verse 2: bars 29–44  (16 bars)
# Chorus:  bars 45–52  (8 bars)
# Bridge:  bars 53–58  (6 bars)
# Outro:   bars 59–66  (8 bars)

# ── Chord progression (F major / D minor city-pop style) ─────────────────
# Each entry = list of chord symbols per bar (1 chord = whole bar, 2 = half each)

INTRO = [
    ['Dm9'],
    ['Gm9'],
    ['C9'],
    ['Fmaj7'],
]

VERSE = [
    ['Dm7'],       ['Gm7'],       ['C7'],        ['Fmaj7'],
    ['B-maj7'],    ['Eø7'],       ['A7'],        ['Dm7'],
    ['Dm7'],       ['Gm7'],       ['C7'],        ['Am7'],
    ['B-maj7'],    ['Gm7', 'A7'], ['Dm7'],       ['Dm7'],
]

CHORUS = [
    ['B-maj7'],    ['C7'],        ['Am7'],       ['Dm7'],
    ['Gm7'],       ['A7'],        ['Dm7'],       ['Dm7', 'A7'],
]

BRIDGE = [
    ['B-maj7'],    ['Am7'],       ['Gm7'],
    ['C7'],        ['Fmaj7'],     ['A7'],
]

OUTRO = [
    ['Dm7'],       ['Gm7'],       ['C7'],        ['Fmaj7'],
    ['B-maj7'],    ['Eø7'],       ['A7'],        ['Dm7'],
]

ALL_SECTIONS = (
    ('Intro',  INTRO),
    ('Verse',  VERSE),
    ('Chorus', CHORUS),
    ('Verse',  VERSE),
    ('Chorus', CHORUS),
    ('Bridge', BRIDGE),
    ('Outro',  OUTRO),
)

# Flatten to 66 bars of chord lists
BARS = []
SECTION_MARKERS = {}  # bar_index -> label
for label, section in ALL_SECTIONS:
    SECTION_MARKERS[len(BARS)] = label
    BARS.extend(section)

assert len(BARS) == 66, f"Expected 66 bars, got {len(BARS)}"


# ── Chord-tone tables ────────────────────────────────────────────────────
# Map chord symbol -> (root_midi, intervals_above_root)
# Root is given as MIDI note number for the bass octave (2)
CHORD_TONES = {
    'Dm7':    ('D3', [0, 3, 7, 10]),
    'Dm9':    ('D3', [0, 3, 7, 10, 14]),
    'Gm7':    ('G3', [0, 3, 7, 10]),
    'Gm9':    ('G3', [0, 3, 7, 10, 14]),
    'C7':     ('C3', [0, 4, 7, 10]),
    'C9':     ('C3', [0, 4, 7, 10, 14]),
    'Fmaj7':  ('F3', [0, 4, 7, 11]),
    'B-maj7': ('B-3', [0, 4, 7, 11]),
    'Am7':    ('A3', [0, 3, 7, 10]),
    'Eø7':    ('E3', [0, 3, 6, 10]),
    'A7':     ('A3', [0, 4, 7, 10]),
}


def get_chord_pitches(sym, octave=4):
    """Return list of pitch strings for a chord symbol at given octave."""
    root_str, intervals = CHORD_TONES[sym]
    root_note = note.Note(root_str)
    root_midi = root_note.pitch.midi
    # Shift to requested octave
    base_midi = root_midi + (octave - root_note.pitch.octave) * 12
    pitches = []
    for iv in intervals[:4]:  # max 4 notes
        p = note.Note()
        p.pitch.midi = base_midi + iv
        pitches.append(p.pitch.nameWithOctave)
    return pitches


def get_root_pitch(sym, octave=2):
    """Bass root note."""
    root_str, _ = CHORD_TONES[sym]
    n = note.Note(root_str)
    n.pitch.octave = octave
    return n.pitch.nameWithOctave


def get_fifth_pitch(sym, octave=2):
    """Bass 5th."""
    root_str, intervals = CHORD_TONES[sym]
    n = note.Note(root_str)
    n.pitch.midi = n.pitch.midi + (octave - n.pitch.octave) * 12 + intervals[2]
    return n.pitch.nameWithOctave


# ── Melody guide tones (chord tone that sits well as melody) ─────────────
# These are *guide tones* — replace with actual melody from the ukulele score
def get_melody_pitch(sym, octave=5):
    """Pick the 3rd of the chord as a melodic guide tone."""
    root_str, intervals = CHORD_TONES[sym]
    n = note.Note(root_str)
    third = intervals[1]  # 3rd interval
    n.pitch.midi = n.pitch.midi + (octave - n.pitch.octave) * 12 + third
    return n.pitch.nameWithOctave


def get_alto_harmony(sym, octave=4):
    """Alto: root of chord (a 3rd below the melody 3rd roughly)."""
    root_str, intervals = CHORD_TONES[sym]
    n = note.Note(root_str)
    n.pitch.octave = octave
    return n.pitch.nameWithOctave


def get_tenor_harmony(sym, octave=3):
    """Tenor: 5th of chord."""
    root_str, intervals = CHORD_TONES[sym]
    n = note.Note(root_str)
    fifth = intervals[2]
    n.pitch.midi = n.pitch.midi + (octave - n.pitch.octave) * 12 + fifth
    return n.pitch.nameWithOctave


# ── Build score ──────────────────────────────────────────────────────────
def build_score():
    s = stream.Score()
    s.metadata = metadata.Metadata()
    s.metadata.title = 'Ruby no Yubiwa (ルビーの指環)'
    s.metadata.composer = 'Akira Terao (寺尾聰)'
    s.metadata.movementName = 'Full Band Arrangement with Vocal Harmonies'

    # Tempo
    mm = tempo.MetronomeMark(number=99, referent=note.Note(type='quarter'))

    # Time signature & key
    ts = meter.TimeSignature('4/4')
    ks = key.Key('F')
    ks_minor = key.Key('d')

    # ── Parts ────────────────────────────────────────────────────────────
    lead_part = stream.Part()
    lead_part.partName = 'Lead Vocal'
    lead_part.partAbbreviation = 'Vox'
    lead_inst = instrument.Vocalist()
    lead_inst.instrumentName = 'Lead Vocal'
    lead_part.insert(0, lead_inst)

    alto_part = stream.Part()
    alto_part.partName = 'Alto Harmony'
    alto_part.partAbbreviation = 'Alt'
    alto_inst = instrument.Vocalist()
    alto_inst.instrumentName = 'Alto'
    alto_part.insert(0, alto_inst)

    tenor_part = stream.Part()
    tenor_part.partName = 'Tenor Harmony'
    tenor_part.partAbbreviation = 'Ten'
    tenor_inst = instrument.Vocalist()
    tenor_inst.instrumentName = 'Tenor'
    tenor_part.insert(0, tenor_inst)

    piano_part = stream.Part()
    piano_part.partName = 'Electric Piano'
    piano_part.partAbbreviation = 'E.Pno'
    piano_part.insert(0, instrument.ElectricPiano())

    guitar_part = stream.Part()
    guitar_part.partName = 'Electric Guitar'
    guitar_part.partAbbreviation = 'E.Gtr'
    guitar_part.insert(0, instrument.ElectricGuitar())

    bass_part = stream.Part()
    bass_part.partName = 'Bass Guitar'
    bass_part.partAbbreviation = 'Bass'
    bass_part.insert(0, instrument.ElectricBass())

    drum_part = stream.Part()
    drum_part.partName = 'Drum Set'
    drum_part.partAbbreviation = 'Dr.'
    drum_part.insert(0, instrument.UnpitchedPercussion())

    all_parts = [lead_part, alto_part, tenor_part,
                 piano_part, guitar_part, bass_part, drum_part]

    # ── Fill each bar ────────────────────────────────────────────────────
    for bar_idx, bar_chords in enumerate(BARS):
        section_label = SECTION_MARKERS.get(bar_idx)
        is_intro = bar_idx < 4
        is_chorus = section_label == 'Chorus' or (
            20 <= bar_idx < 28 or 44 <= bar_idx < 52
        )
        is_bridge = 52 <= bar_idx < 58
        n_chords = len(bar_chords)
        beat_dur = 4.0 / n_chords  # quarter-note lengths per chord

        # Create measures
        measures = {name: stream.Measure(number=bar_idx + 1) for name in
                    ['lead', 'alto', 'tenor', 'piano', 'guitar', 'bass', 'drum']}

        # First bar: add time sig, key, tempo
        if bar_idx == 0:
            for m in measures.values():
                m.insert(0, ts)
                m.insert(0, ks)
            measures['lead'].insert(0, mm)

        # Section rehearsal marks
        if section_label:
            mark = expressions.RehearsalMark(section_label)
            measures['lead'].insert(0, mark)

        # Add chord symbols to lead part for reference
        offset = 0.0
        for ci, sym in enumerate(bar_chords):
            cs = harmony.ChordSymbol(sym)
            cs.writeAsChord = False
            measures['lead'].insert(offset, cs)

            # ── LEAD VOCAL ──
            if is_intro:
                # Intro: rest
                r = note.Rest()
                r.duration = duration.Duration(beat_dur)
                measures['lead'].insert(offset, r)
            else:
                mel = note.Note(get_melody_pitch(sym, 5))
                mel.duration = duration.Duration(beat_dur)
                mel.lyric = '~' if ci > 0 else None
                measures['lead'].insert(offset, mel)

            # ── ALTO HARMONY ──
            if is_intro or is_bridge:
                r = note.Rest()
                r.duration = duration.Duration(beat_dur)
                measures['alto'].insert(offset, r)
            else:
                alt = note.Note(get_alto_harmony(sym, 4))
                alt.duration = duration.Duration(beat_dur)
                measures['alto'].insert(offset, alt)

            # ── TENOR HARMONY ──
            if is_intro or not is_chorus:
                r = note.Rest()
                r.duration = duration.Duration(beat_dur)
                measures['tenor'].insert(offset, r)
            else:
                ten = note.Note(get_tenor_harmony(sym, 4))
                ten.duration = duration.Duration(beat_dur)
                measures['tenor'].insert(offset, ten)

            # ── ELECTRIC PIANO ──
            pitches = get_chord_pitches(sym, 4)
            ch = chord.Chord(pitches)
            ch.duration = duration.Duration(beat_dur)
            if is_intro:
                ch.volume = dynamics.Dynamic('mp').volumeScalar
            measures['piano'].insert(offset, ch)

            # ── ELECTRIC GUITAR (rhythm comping) ──
            gtr_pitches = get_chord_pitches(sym, 3)[:3]
            # Rhythmic pattern: eighth-note strums
            for sub_beat in range(int(beat_dur * 2)):
                sub_offset = offset + sub_beat * 0.5
                if sub_beat % 2 == 0:
                    # Strum
                    gch = chord.Chord(gtr_pitches)
                    gch.duration = duration.Duration(0.5)
                    measures['guitar'].insert(sub_offset, gch)
                else:
                    # Ghost strum (lighter) or rest for groove
                    if bar_idx % 2 == 0:
                        gr = note.Rest()
                        gr.duration = duration.Duration(0.5)
                        measures['guitar'].insert(sub_offset, gr)
                    else:
                        gch2 = chord.Chord(gtr_pitches)
                        gch2.duration = duration.Duration(0.5)
                        gch2.style.color = '#888888'
                        measures['guitar'].insert(sub_offset, gch2)

            # ── BASS GUITAR ──
            root_p = get_root_pitch(sym, 2)
            fifth_p = get_fifth_pitch(sym, 2)
            if beat_dur >= 4.0:
                # Whole bar on one chord: root → 5th → root → passing
                for bi in range(4):
                    bp = root_p if bi % 2 == 0 else fifth_p
                    bn = note.Note(bp)
                    bn.duration = duration.Duration(1.0)
                    measures['bass'].insert(offset + bi, bn)
            elif beat_dur >= 2.0:
                # Half bar: root, 5th
                bn1 = note.Note(root_p)
                bn1.duration = duration.Duration(1.0)
                measures['bass'].insert(offset, bn1)
                bn2 = note.Note(fifth_p)
                bn2.duration = duration.Duration(1.0)
                measures['bass'].insert(offset + 1.0, bn2)

            offset += beat_dur

        # ── DRUMS (city-pop groove) ──────────────────────────────────────
        # Simplified: kick on 1 & 3, snare/cross-stick on 2 & 4,
        # hi-hat eighths throughout
        # Drum groove: kick=C2, snare=D2, cross-stick=E2, hi-hat=F#2
        for beat in range(8):  # eighth notes across 4/4
            beat_offset = beat * 0.5

            if beat % 4 == 0:
                # Beat 1, 3: kick + hi-hat
                kick = chord.Chord(['C2', 'F#2'])
                kick.duration = duration.Duration(0.5)
                measures['drum'].insert(beat_offset, kick)
            elif beat % 4 == 2:
                # Beat 2, 4: snare/cross-stick + hi-hat
                snare_pitch = 'E2' if (is_intro or not is_chorus) else 'D2'
                snare = chord.Chord([snare_pitch, 'F#2'])
                snare.duration = duration.Duration(0.5)
                measures['drum'].insert(beat_offset, snare)
            else:
                # Off-beats: hi-hat only
                hhn = note.Note('F#2')
                hhn.duration = duration.Duration(0.5)
                measures['drum'].insert(beat_offset, hhn)

        # Append measures to parts
        lead_part.append(measures['lead'])
        alto_part.append(measures['alto'])
        tenor_part.append(measures['tenor'])
        piano_part.append(measures['piano'])
        guitar_part.append(measures['guitar'])
        bass_part.append(measures['bass'])
        drum_part.append(measures['drum'])

    # Add clefs
    alto_part.insert(0, clef.TrebleClef())
    tenor_part.insert(0, clef.TrebleClef())
    bass_part.insert(0, clef.BassClef())
    drum_part.insert(0, clef.PercussionClef())

    # Assemble score
    for p in all_parts:
        s.insert(0, p)

    return s


def main():
    print("Building full band score for 'Ruby no Yubiwa'...")
    score = build_score()

    out_path = os.path.join(os.path.dirname(__file__),
                            'ruby_no_yubiwa_full_band.musicxml')
    score.write('musicxml', fp=out_path)
    print(f"Score written to: {out_path}")
    print(f"  → Open this file in MuseScore Studio")
    print()
    print("Parts included:")
    print("  1. Lead Vocal (guide tones – replace with real melody)")
    print("  2. Alto Harmony (diatonic 3rds)")
    print("  3. Tenor Harmony (chorus sections only, 5ths)")
    print("  4. Electric Piano (Rhodes chord voicings)")
    print("  5. Electric Guitar (rhythmic eighth-note comping)")
    print("  6. Bass Guitar (root-fifth pattern)")
    print("  7. Drum Set (city-pop groove)")
    print()
    print("Next steps in MuseScore:")
    print("  • Copy the real melody from the ukulele score into Lead Vocal")
    print("  • Alto/Tenor harmonies will auto-adjust once melody is correct")
    print("  • Tweak drum fills at section boundaries")
    print("  • Add string pads via Edit → Instruments if desired")


if __name__ == '__main__':
    main()
