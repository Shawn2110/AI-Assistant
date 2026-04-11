"""Audio capture module - continuous microphone input as async chunk stream."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import numpy as np
import sounddevice as sd

from src.core.exceptions import VoiceError


class AudioCapture:
    """Captures audio from the microphone and yields chunks asynchronously.

    Audio format: 16-bit PCM at the configured sample rate (default 16kHz mono),
    which is the format required by both Vosk and openwakeword.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: int | None = None,
        chunk_duration_ms: int = 100,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self._running = False
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self._stream: sd.InputStream | None = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Called by sounddevice for each audio block. Puts data on the async queue."""
        if status:
            pass  # Drop status warnings silently in MVP
        try:
            self._queue.put_nowait(indata.copy())
        except asyncio.QueueFull:
            pass  # Drop frames if consumer is too slow

    async def start(self) -> None:
        """Open the microphone stream. Raises VoiceError if no mic available."""
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device,
                blocksize=self.chunk_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._running = True
        except Exception as exc:
            raise VoiceError(f"Could not open microphone: {exc}") from exc

    def stop(self) -> None:
        """Stop capturing audio."""
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    async def _read_chunks(self) -> AsyncIterator[np.ndarray]:
        """Internal generator that reads from the queue while running."""
        while self._running:
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield chunk
            except asyncio.TimeoutError:
                continue

    async def stream(self) -> AsyncIterator[np.ndarray]:
        """Start capturing and yield audio chunks.

        Usage::

            capture = AudioCapture()
            async for chunk in capture.stream():
                process(chunk)
        """
        await self.start()
        try:
            async for chunk in self._read_chunks():
                yield chunk
        finally:
            self.stop()
