"""Transcription buffer processor for dictation.

Buffers transcription text until the user explicitly stops recording,
then emits a single consolidated transcription for LLM cleanup.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from pipecat.frames.frames import (
    Frame,
    InputTransportMessageFrame,
    OutputTransportMessageFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transcriptions.language import Language

from utils.logger import logger

# Maximum time to wait for pending transcription when stop-recording is received
# and speech was detected but buffer is empty (STT still processing)
TRANSCRIPTION_WAIT_TIMEOUT_SECONDS = 0.8
# Interval to poll for transcription arrival
TRANSCRIPTION_POLL_INTERVAL_SECONDS = 0.05


class TranscriptionBufferProcessor(FrameProcessor):
    """Buffers transcriptions until user stops recording.

    This processor accumulates transcription text from partial STT results
    and emits a single consolidated TranscriptionFrame when the client sends
    a 'stop-recording' message. This allows the LLM cleanup to process
    complete utterances instead of fragments.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the transcription buffer processor."""
        super().__init__(**kwargs)
        self._buffer: str = ""
        self._last_user_id: str = "user"
        self._last_language: Language | None = None
        # Track whether VAD detected speech since start-recording
        self._speech_detected: bool = False
        # Event to signal transcription has arrived (for waiting on slow STT)
        self._transcription_arrived: asyncio.Event = asyncio.Event()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process frames, buffering transcriptions until stop-recording message.

        Args:
            frame: The frame to process
            direction: The direction of frame flow
        """
        await super().process_frame(frame, direction)

        # Track speech activity from VAD
        if isinstance(frame, UserStartedSpeakingFrame):
            self._speech_detected = True
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            # Accumulate transcription text and save metadata
            text = frame.text
            if text:
                self._buffer += text
                self._last_user_id = frame.user_id
                self._last_language = frame.language
                # Signal that transcription has arrived (for waiting stop-recording)
                self._transcription_arrived.set()
                logger.debug(f"Buffered transcription: '{text}' (total: '{self._buffer}')")
            # Don't push TranscriptionFrame - we'll emit consolidated version later
            return

        if isinstance(frame, InputTransportMessageFrame):
            # Extract message type from the transport message payload
            # RTVI client-message format: {"type": "client-message", "data": {"t": "start-recording", "d": {}}}
            message = frame.message
            message_type = None
            if isinstance(message, dict):
                outer_type = message.get("type")
                if outer_type == "client-message":
                    # Nested message - extract inner type from "t" field
                    data = message.get("data", {})
                    if isinstance(data, dict):
                        message_type = data.get("t")  # RTVI uses "t" for type
                else:
                    message_type = outer_type
            logger.info(f"Received client message: type={message_type}")

            if message_type == "start-recording":
                # New recording session - reset all state
                logger.info("Start-recording received, resetting state")
                self._buffer = ""
                self._last_user_id = "user"
                self._last_language = None
                self._speech_detected = False
                self._transcription_arrived.clear()
                return

            if message_type == "stop-recording":
                # Client explicitly stopped recording - flush the buffer
                if self._buffer.strip():
                    logger.info(
                        f"Stop-recording received, flushing buffer: '{self._buffer.strip()}'"
                    )
                    await self._emit_transcription(direction)
                elif self._speech_detected:
                    # Speech was detected but buffer is empty - STT may still be processing
                    # Wait for transcription to arrive with timeout
                    logger.info(
                        "Stop-recording received, speech detected but buffer empty, waiting for STT..."
                    )
                    await self._wait_for_transcription(direction)
                else:
                    # No speech detected - send empty response immediately
                    logger.info("Stop-recording received, no speech detected, sending empty response")
                    await self._emit_empty_response(direction)

                # Always reset state
                self._reset_state()
                # Don't pass through the client message frame
                return

        # Pass through all other frames unchanged
        await self.push_frame(frame, direction)

    async def _emit_transcription(self, direction: FrameDirection) -> None:
        """Emit the buffered transcription as a consolidated frame."""
        timestamp = datetime.now(UTC).isoformat()
        consolidated_frame = TranscriptionFrame(
            text=self._buffer.strip(),
            user_id=self._last_user_id,
            timestamp=timestamp,
            language=self._last_language,
        )
        await self.push_frame(consolidated_frame, direction)

    async def _emit_empty_response(self, direction: FrameDirection) -> None:
        """Send an empty response message to the client."""
        empty_response_message = {
            "label": "rtvi-ai",
            "type": "server-message",
            "data": {"type": "recording-complete", "hasContent": False},
        }
        await self.push_frame(
            OutputTransportMessageFrame(message=empty_response_message), direction
        )

    async def _wait_for_transcription(self, direction: FrameDirection) -> None:
        """Wait for transcription to arrive from STT with timeout.

        Polls for transcription arrival at regular intervals. If transcription
        arrives within the timeout, emits it. Otherwise, sends empty response.
        """
        elapsed = 0.0
        while elapsed < TRANSCRIPTION_WAIT_TIMEOUT_SECONDS:
            # Check if transcription arrived
            if self._buffer.strip():
                logger.info(
                    f"Transcription arrived after {elapsed:.0f}ms: '{self._buffer.strip()}'"
                )
                await self._emit_transcription(direction)
                return

            # Wait a short interval before checking again
            await asyncio.sleep(TRANSCRIPTION_POLL_INTERVAL_SECONDS)
            elapsed += TRANSCRIPTION_POLL_INTERVAL_SECONDS

        # Timeout - no transcription arrived
        logger.warning(
            f"Timeout waiting for transcription after {TRANSCRIPTION_WAIT_TIMEOUT_SECONDS}s"
        )
        await self._emit_empty_response(direction)

    def _reset_state(self) -> None:
        """Reset all buffer state for next recording session."""
        self._buffer = ""
        self._last_user_id = "user"
        self._last_language = None
        self._speech_detected = False
        self._transcription_arrived.clear()
