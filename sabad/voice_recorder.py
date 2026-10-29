"""Browser-side voice recorder for serverless Streamlit deployments.

``st.audio_input`` stores the finished recording through Streamlit's internal
multipart upload endpoint. That endpoint is not reliable behind a Vercel
Python Function, so this component keeps the short recording in memory and
returns a compact base64 payload through the normal component state channel.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

import streamlit as st


_HTML = """
<div class="sabad-voice-recorder" dir="rtl">
  <button class="record-button" type="button" aria-label="ضبط لیست خرید">
    <span class="record-icon" aria-hidden="true">●</span>
    <span class="record-label">ضبط لیست خرید</span>
  </button>
  <div class="record-status" role="status" aria-live="polite"></div>
</div>
"""

_CSS = """
:host { display: block; width: 100%; }
.sabad-voice-recorder {
  display: grid;
  justify-items: center;
  gap: 10px;
  color: var(--st-text-color, #102a43);
  font-family: var(--st-font-family, sans-serif);
}
.record-button {
  width: 190px;
  min-height: 62px;
  border: 0;
  border-radius: 999px;
  background: var(--st-primary-color, #0b8f78);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  font-size: 1rem;
  box-shadow: 0 12px 28px rgba(11, 143, 120, .22);
  transition: transform .16s ease, background .16s ease, box-shadow .16s ease;
}
.record-button:hover { transform: translateY(-1px); box-shadow: 0 15px 32px rgba(11, 143, 120, .28); }
.record-button:focus-visible { outline: 3px solid #72cbb8; outline-offset: 4px; }
.record-button.recording { background: #d94747; box-shadow: 0 0 0 10px rgba(217, 71, 71, .12); }
.record-icon {
  width: 17px;
  height: 17px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  background: currentColor;
  color: #fff;
  font-size: 0;
}
.recording .record-icon { border-radius: 4px; width: 15px; height: 15px; }
.record-status { min-height: 1.5em; color: var(--st-text-color, #627d98); font-size: .85rem; text-align: center; }
"""

_JS = r"""
export default function (component) {
  const { parentElement, setTriggerValue } = component
  const root = parentElement.querySelector(".sabad-voice-recorder")
  const button = root?.querySelector(".record-button")
  const label = root?.querySelector(".record-label")
  const status = root?.querySelector(".record-status")
  if (!root || !button || !label || !status) return

  let recorder = null
  let chunks = []
  let startedAt = 0

  const setIdle = () => {
    button.classList.remove("recording")
    label.textContent = "ضبط لیست خرید"
    button.disabled = false
  }

  const setError = (message) => {
    setIdle()
    status.textContent = message
  }

  const toBase64 = (arrayBuffer) => {
    const bytes = new Uint8Array(arrayBuffer)
    let binary = ""
    const chunkSize = 0x8000
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize))
    }
    return btoa(binary)
  }

  const finishRecording = async () => {
    button.disabled = true
    const blob = new Blob(chunks, { type: recorder?.mimeType || "audio/webm" })
    if (!blob.size) {
      setError("صدایی ضبط نشد. دوباره امتحان کن.")
      return
    }
    status.textContent = "در حال آماده‌سازی صدا…"
    try {
      const data = toBase64(await blob.arrayBuffer())
      setTriggerValue("recording", {
        data,
        mimeType: blob.type || "audio/webm",
        durationMs: Math.max(0, Date.now() - startedAt),
      })
      setIdle()
      status.textContent = "ضبط شد؛ در حال تبدیل به متن…"
    } catch (error) {
      setError("ارسال صدا انجام نشد. دوباره ضبط کن.")
    }
  }

  const stop = () => {
    if (recorder && recorder.state !== "inactive") recorder.stop()
  }

  const start = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("مرورگر شما ضبط صدا را پشتیبانی نمی‌کند.")
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]
      const supportsType = typeof window.MediaRecorder.isTypeSupported === "function"
        ? (type) => window.MediaRecorder.isTypeSupported(type)
        : () => false
      const mimeType = preferredTypes.find(supportsType) || ""
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      chunks = []
      startedAt = Date.now()
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data) }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        finishRecording()
      }
      recorder.start()
      button.classList.add("recording")
      label.textContent = "پایان ضبط"
      status.textContent = "دارم گوش می‌دهم…"
    } catch (error) {
      setError("دسترسی به میکروفون ممکن نیست.")
    }
  }

  button.onclick = () => {
    if (recorder && recorder.state === "recording") stop()
    else start()
  }

  return () => {
    if (recorder && recorder.state !== "inactive") recorder.stop()
    recorder = null
  }
}
"""


_VOICE_RECORDER = st.components.v2.component(
    "sabad_voice_recorder",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def voice_recorder(
    *,
    key: str,
    on_recording_change: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    """Render the browser recorder and return its latest recording payload."""

    result = _VOICE_RECORDER(
        key=key,
        data={"version": 1},
        on_recording_change=on_recording_change or (lambda: None),
        width="stretch",
        height="content",
    )
    payload = getattr(result, "recording", None)
    return payload if isinstance(payload, dict) else None


def decode_recording(payload: dict[str, Any]) -> tuple[bytes, str] | None:
    """Validate and decode a component payload without trusting its metadata."""

    if not isinstance(payload, dict):
        return None
    encoded = payload.get("data")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        audio_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        return None
    if not audio_bytes:
        return None
    mime_type = payload.get("mimeType")
    if not isinstance(mime_type, str) or not mime_type.startswith("audio/"):
        mime_type = "audio/webm"
    return audio_bytes, mime_type.split(";", 1)[0]


__all__ = ["decode_recording", "voice_recorder"]
