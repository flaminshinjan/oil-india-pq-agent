"""Construct one Pipecat pipeline per browser connection.

The pipeline:
  FastAPIWebsocketTransport.input()      ← browser mic (PCM)
    → SileroVADAnalyzer                  ← speech vs silence
    → DeepgramSTTService                 ← interim + final transcripts
    → context aggregator (user)          ← appends user turn to LLM ctx
    → AnthropicLLMService                ← streams the reply
    → CartesiaTTSService                 ← streams audio out
    → context aggregator (assistant)     ← appends assistant turn to ctx
  FastAPIWebsocketTransport.output()     → browser speaker

The PIPECAT_SYSTEM_PROMPT keeps the assistant on topic, advisory-only, and
brief — voice conversations want shorter replies than text chat.

API keys come from env: DEEPGRAM_API_KEY, CARTESIA_API_KEY, ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import os

from fastapi import WebSocket
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    AudioRawFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    StartFrame,
    TranscriptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.serializers.base_serializer import FrameSerializer, FrameSerializerType
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

try:
    from deepgram import LiveOptions
except Exception:  # noqa: BLE001
    LiveOptions = None  # type: ignore

from ..retrieval.vectorstore import get_store


class RawAudioSerializer(FrameSerializer):
    """Browser ↔ Pipecat over a WebSocket carrying raw PCM bytes.

    Inbound  (browser → server): each binary WebSocket frame is a chunk of
                                  16 kHz, 16-bit, mono PCM. We wrap it in
                                  an InputAudioRawFrame for the STT.
    Outbound (server → browser): every AudioRawFrame emitted by the TTS is
                                  written back as the raw PCM bytes. The
                                  client AudioContext plays them at the
                                  output sample rate.
    """

    def __init__(self, *, in_sample_rate: int = 16_000, out_sample_rate: int = 24_000):
        self._in_sample_rate = in_sample_rate
        self._out_sample_rate = out_sample_rate

    @property
    def type(self) -> FrameSerializerType:
        return FrameSerializerType.BINARY

    async def setup(self, frame: StartFrame) -> None:
        # No protocol handshake — both sides agreed on PCM rates already.
        return None

    async def serialize(self, frame: Frame) -> str | bytes | None:
        # Drop everything except audio frames coming from TTS.
        if isinstance(frame, AudioRawFrame):
            return frame.audio
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, (bytes, bytearray)):
            return InputAudioRawFrame(
                audio=bytes(data),
                sample_rate=self._in_sample_rate,
                num_channels=1,
            )
        return None

class TranscriptTap(FrameProcessor):
    """Pass-through processor that copies user transcripts and assistant
    text to the WebSocket as JSON control frames.

    Inserted twice in the pipeline:
      1. Right after STT  → catches `TranscriptionFrame`s from the user.
      2. Right after LLM  → buffers `LLMTextFrame`s until end-of-response,
                            then emits the full assistant turn.
    Frames flow downstream untouched — the tap is purely observational.
    """

    def __init__(self, websocket: WebSocket):
        super().__init__()
        self._ws = websocket
        self._assistant_buf: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (getattr(frame, "text", "") or "").strip()
            if text:
                logger.info(f"[voice] user (final): {text}")
                await self._send({"type": "transcript", "role": "user", "text": text, "final": True})
        elif isinstance(frame, InterimTranscriptionFrame):
            text = (getattr(frame, "text", "") or "").strip()
            if text:
                await self._send({"type": "transcript", "role": "user", "text": text, "final": False})
        elif isinstance(frame, LLMTextFrame):
            chunk = getattr(frame, "text", "") or ""
            if chunk:
                self._assistant_buf.append(chunk)
        elif isinstance(frame, LLMFullResponseEndFrame):
            text = "".join(self._assistant_buf).strip()
            self._assistant_buf.clear()
            if text:
                logger.info(f"[voice] ai (final): {text}")
                await self._send({"type": "transcript", "role": "ai", "text": text, "final": True})

        await self.push_frame(frame, direction)

    async def _send(self, payload: dict) -> None:
        try:
            await self._ws.send_text(json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[voice] transcript send failed: {exc}")


class RagInjector(FrameProcessor):
    """Pre-LLM hook: rewrites the most recent user message to inline the
    most relevant Chroma chunks. The model then answers with the same
    grounding the chat panel uses (annual reports, PQ replies, etc.).

    We mutate the LAST user message's content from
        "what's our LTIFR?"
    to
        "[Relevant OIL data:\n …chunks… ]\n\nQuestion: what's our LTIFR?"
    so Anthropic gets context inline without needing tool-calling.
    """

    def __init__(self, *, k_db: int = 4, k_pq: int = 2, max_chars: int = 2400):
        super().__init__()
        self._k_db = k_db
        self._k_pq = k_pq
        self._max_chars = max_chars
        try:
            self._store = get_store()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[voice] RAG store unavailable: {exc}")
            self._store = None
        self._last_injected_text: str | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if self._store is not None and isinstance(frame, OpenAILLMContextFrame):
            try:
                ctx = frame.context
                messages = ctx.messages
                last_user_idx = None
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        last_user_idx = i
                        break

                if last_user_idx is not None:
                    raw = messages[last_user_idx].get("content")
                    user_text = raw if isinstance(raw, str) else None
                    if user_text and user_text != self._last_injected_text:
                        # Avoid re-running RAG on the same user message if
                        # the LLM re-enters with the same context.
                        self._last_injected_text = user_text

                        # Skip RAG entirely for short conversational turns
                        # (greetings, acks, "go on"). The Chroma + embedder
                        # round-trip costs ~150-250 ms per call — for "hi"
                        # it's pure latency tax, no benefit.
                        if not self._should_search(user_text):
                            logger.info(f"[voice] RAG skipped (conversational): {user_text!r}")
                        else:
                            rag_blob = self._build_rag_blob(user_text)
                            if rag_blob:
                                messages[last_user_idx] = {
                                    "role": "user",
                                    "content": (
                                        "[Relevant OIL data — use ONLY this to answer.]\n"
                                        f"{rag_blob}\n"
                                        "[End of context]\n\n"
                                        f"Question: {user_text}"
                                    ),
                                }
                                logger.info(
                                    f"[voice] RAG injected {len(rag_blob)} chars for: {user_text!r}"
                                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[voice] RAG injection failed: {exc}")

        await self.push_frame(frame, direction)

    # Short conversational openers / closers — skip RAG, keeps latency
    # under the 750 ms target.
    _CONVERSATIONAL = {
        "hi", "hey", "hello", "yo", "ok", "okay", "yes", "yep", "yeah",
        "no", "nope", "sure", "right", "thanks", "ta", "bye",
        "go on", "carry on", "continue", "tell me more", "and",
        "got it", "fine", "alright", "good", "great", "lovely",
        "what", "huh", "sorry", "say again", "repeat",
    }

    def _should_search(self, text: str) -> bool:
        """Return True when the user clearly asked for information, not
        just acked or greeted. Heuristic, not perfect — false negatives
        cost answer quality, false positives cost ~200 ms of latency."""
        t = (text or "").strip().lower().rstrip("?.,!")
        if not t:
            return False
        if t in self._CONVERSATIONAL:
            return False
        # Anything 3+ words OR ending in a question mark probably wants RAG.
        if "?" in text:
            return True
        words = t.split()
        if len(words) >= 4:
            return True
        # Short questions like "what's our LTIFR?" don't always have a
        # question mark — gate on info-seeking verbs.
        info_words = {"how", "what", "why", "when", "where", "tell", "show",
                      "give", "explain", "compare", "list", "find", "any",
                      "anything", "status", "trend", "data", "number"}
        return any(w in info_words for w in words)

    def _build_rag_blob(self, query: str) -> str:
        hits = []
        try:
            hits = list(self._store.search("db", query, k=self._k_db))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[voice] db search failed: {exc}")
        try:
            hits.extend(self._store.search("pq", query, k=self._k_pq))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[voice] pq search failed: {exc}")
        if not hits:
            return ""

        hits.sort(key=lambda h: h.score, reverse=True)
        parts: list[str] = []
        used = 0
        for h in hits:
            fname = (h.metadata or {}).get("filename") or (h.metadata or {}).get("source") or "doc"
            text = (h.text or "").strip().replace("\n\n", "\n")
            if not text:
                continue
            piece = f"[{fname}] {text[:500]}"
            if used + len(piece) > self._max_chars:
                break
            parts.append(piece)
            used += len(piece)
        return "\n\n".join(parts)


from ..config import settings


# Voice replies need to be short and conversational — the dashboard
# already shows the structured data. Keep Digby's "advisory only"
# positioning explicit.
PIPECAT_SYSTEM_PROMPT = """You are Digby — the conversational voice of an
advisory intelligence layer for Oil India Limited (OIL). (You are named
after Digboi, Assam, the birthplace of Asia's oil industry.) If asked who
you are, say you're Digby.

How to answer:
- Lead with the actual number or fact. Be concrete.
- Two to three short sentences. Plain spoken British-Indian English,
  no markdown, no lists.
- When a [Relevant OIL data] block precedes the question, ground every
  number in it. When it doesn't, answer from general OIL knowledge
  (annual report, BRSR, ESG, 10-yr data) — give the user a useful
  answer rather than deferring. Do NOT invent specific figures you
  can't justify, but DO synthesise the picture.
- For any growth %, CAGR or ratio, do the arithmetic carefully from the
  exact figures — never guess a percentage.
- Treat the user like a senior executive — concise, confident, no
  hedging unless the data genuinely conflicts.

Topics in scope: production (crude / gas, MMT / BCM), reserves (1P/2P,
RRR), drilling (wells planned vs drilled), HSE (LTIFR, PPE events),
workforce, finance, and OIL's annual / BRSR / ESG reports.

You are advisory only — never act, never promise anything.
"""


# Cartesia "Sonic English Lady" voice — calm, business-news cadence.
# Override at deploy time via CARTESIA_VOICE_ID env if a different voice
# is preferred.
DEFAULT_CARTESIA_VOICE = "79a125e8-cd45-4c13-8a67-188112f4dd22"


DOMAIN_HINTS = {
    "brief":       "The user is viewing the executive brief.",
    "production":  "The user is on the Production dashboard — bias answers toward crude/gas, MMT/MMSCM, plan-vs-achievement and year-on-year trends.",
    "exploration": "The user is on the Exploration & Drilling dashboard — bias toward wells drilled, exploratory vs development, reserves, RRR, Andaman.",
    "hse":         "The user is on the HSE / Safety dashboard — bias toward PPE event counts, LTIFR, by-site / by-shift patterns.",
    "hr":          "The user is on the HR / Workforce dashboard — bias toward headcount, attrition, open requisitions, time-to-fill by function.",
    "procurement": "The user is on the Procurement dashboard — bias toward vendor bids, price/delivery/warranty, deviation severity.",
}


async def run_voice_session(websocket: WebSocket, domain: str | None = None) -> None:
    """Drive one full voice conversation. Returns when the WebSocket closes.

    `domain` is the dashboard the user is currently viewing; we append a
    one-line hint to the system prompt so 'what about this quarter?'
    resolves without naming the topic."""

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    anthropic_key = settings.anthropic_api_key

    if not (deepgram_key and cartesia_key and anthropic_key):
        await websocket.close(code=1011, reason="voice keys not configured")
        return

    # Balanced VAD — 700 ms stop_secs keeps natural clause pauses on the
    # same turn ("can you tell me … how exploration … is going") instead
    # of fragmenting them into three separate user messages. min_volume
    # bumped to 0.7 so background hum / breathing during TTS playback
    # doesn't trigger spurious "user speaking" interruptions that chop
    # the bot's audio.
    vad_analyzer = SileroVADAnalyzer(
        params=VADParams(start_secs=0.2, stop_secs=0.7, confidence=0.7,
                         min_volume=0.7),
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=vad_analyzer,
            vad_audio_passthrough=True,
            serializer=RawAudioSerializer(
                in_sample_rate=16_000,
                out_sample_rate=24_000,
            ),
        ),
    )

    # Deepgram: hold finals until the user actually pauses for ~600 ms;
    # also enable utterance_end_ms so we coalesce hesitations into one
    # transcript rather than the multi-fragment ("Hey. Hi. He hei.") output
    # we saw with defaults. nova-3 + smart_format is already on by default.
    if LiveOptions is not None:
        stt = DeepgramSTTService(
            api_key=deepgram_key,
            live_options=LiveOptions(
                model="nova-3-general",
                language="en",
                encoding="linear16",
                sample_rate=16_000,
                channels=1,
                interim_results=True,
                smart_format=True,
                punctuate=True,
                # Match VAD: 700 ms endpointing + 1500 ms utterance_end
                # for coalescing across natural pauses. The 1000-ms floor
                # on utterance_end_ms must be respected.
                endpointing=700,
                utterance_end_ms="1500",
                vad_events=False,
            ),
        )
    else:
        stt = DeepgramSTTService(api_key=deepgram_key)

    tts = CartesiaTTSService(
        api_key=cartesia_key,
        voice_id=os.getenv("CARTESIA_VOICE_ID", DEFAULT_CARTESIA_VOICE),
    )
    # Always use Haiku 4.5 for voice — sub-second first token vs Sonnet's
    # 1.5–2 s. The conversational replies are 1–2 sentences so quality is
    # fine; latency matters more here than chat-quality reasoning. Cap
    # max_tokens hard so the model can't run long and balloon TTS time.
    llm = AnthropicLLMService(
        api_key=anthropic_key,
        model=os.getenv("ANTHROPIC_VOICE_MODEL", "claude-haiku-4-5-20251001"),
        # 220 tokens ≈ 3 short sentences — enough to actually answer a
        # substantive question instead of deferring to the chat panel.
        params=AnthropicLLMService.InputParams(max_tokens=220),
    )

    system_prompt = PIPECAT_SYSTEM_PROMPT
    if domain and domain in DOMAIN_HINTS:
        system_prompt = system_prompt + "\n\nCurrent context: " + DOMAIN_HINTS[domain]
        logger.info(f"[voice] session domain hint: {domain}")
    context = OpenAILLMContext(
        messages=[{"role": "system", "content": system_prompt}],
    )
    context_aggregator = llm.create_context_aggregator(context)

    rag = RagInjector()
    user_tap = TranscriptTap(websocket)
    ai_tap = TranscriptTap(websocket)

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_tap,
        context_aggregator.user(),
        rag,                          # ← RAG rewrites the last user message
        llm,
        ai_tap,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            # Interruptions OFF — the user complained about choppy audio,
            # which is caused by ambient noise triggering "user speaking"
            # while the bot is mid-sentence. Better to let Digby finish
            # the reply then take the next turn cleanly.
            allow_interruptions=False,
            enable_metrics=False,
            audio_in_sample_rate=16_000,
            audio_out_sample_rate=24_000,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_connect(_transport, _client):
        logger.info("[voice] client connected; waiting for first utterance")

    @transport.event_handler("on_client_disconnected")
    async def on_disconnect(_transport, _client):
        logger.info("[voice] client disconnected")
        await task.queue_frame(EndFrame())

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
