"""Real-time voice pipeline.

Pipecat-based audio pipeline that runs inside the FastAPI app:
  browser mic → WebSocket → Deepgram STT → Anthropic Claude → Cartesia TTS → WebSocket → browser speaker

Each browser connection gets its own pipeline instance with its own LLM
context, so two users can talk to Digby at the same time without their
turns colliding.
"""
