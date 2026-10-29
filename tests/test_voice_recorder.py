import base64

from sabad.voice_recorder import decode_recording


def test_decode_recording_accepts_audio_payload_and_normalizes_mime_type():
    raw = b"browser-recording"
    payload = {
        "data": base64.b64encode(raw).decode("ascii"),
        "mimeType": "audio/webm;codecs=opus",
    }

    assert decode_recording(payload) == (raw, "audio/webm")


def test_decode_recording_rejects_invalid_or_non_audio_payloads():
    assert decode_recording({"data": "not-base64"}) is None
    assert decode_recording({"data": base64.b64encode(b"x").decode(), "mimeType": "text/plain"}) == (
        b"x",
        "audio/webm",
    )
