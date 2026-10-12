"""Deterministic, low-amplitude mono PCM preview. No autoplay."""
import io
import math
import struct
import wave
from .model import Render


def wav_bytes(render, sample_rate=22050):
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 96000:
        raise ValueError("sample_rate must be an integer between 8000 and 96000")
    if render.duration_ms > 60000:
        raise ValueError("Preview duration exceeds 60 seconds")
    length = (render.duration_ms * sample_rate + 999) // 1000
    samples = [0.0] * length
    for event in render.events:
        if event.onset_ms < 0 or event.duration_ms <= 0 or event.onset_ms + event.duration_ms > render.duration_ms:
            raise ValueError("Event lies outside render duration")
        start = event.onset_ms * sample_rate // 1000
        size = event.duration_ms * sample_rate // 1000
        hz = 440 * 2 ** ((event.pitch_cents - 6900) / 1200)
        # The missing marker has two harmonics, an explicit timbral symbol.
        ramp = max(1, min(size // 2, sample_rate * 8 // 1000))
        for i in range(size):
            if start + i >= length:
                break
            phase = 2 * math.pi * hz * i / sample_rate
            envelope = max(0, min(1.0, i / ramp, (size - 1 - i) / ramp))
            tone = math.sin(phase)
            if event.kind in ("missing", "cue_start", "semantic_unknown") or event.kind.endswith("_header"):
                tone = 0.65 * tone + 0.35 * math.sin(2 * phase)
            samples[start + i] += 0.18 * envelope * tone
    data = b"".join(struct.pack("<h", round(max(-1.0, min(1.0, x)) * 32767)) for x in samples)
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(data)
    return output.getvalue()
