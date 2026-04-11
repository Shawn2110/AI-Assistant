# Plan: Build the Voice Pipeline MVP

## Phase 1: Audio Capture & Wake Word Detection

- [ ] Task: Write tests for audio capture module
  - Create `tests/test_audio_capture.py`
  - Test that `AudioCapture` can be instantiated with default and custom device settings
  - Test that audio chunks are emitted in the correct format (16-bit PCM, 16kHz, mono)
  - Test graceful handling when no microphone is available
  - Mock `sounddevice` to avoid hardware dependency in tests

- [ ] Task: Implement audio capture module
  - Create `src/ai_assistant/voice/audio_capture.py`
  - Implement `AudioCapture` class that opens a `sounddevice.InputStream`
  - Emit audio chunks via callback or async generator
  - Add configurable sample rate, channels, and device index
  - Pass all tests from previous task

- [ ] Task: Write tests for wake word detector
  - Create `tests/test_wake_word.py`
  - Test that `WakeWordDetector` loads the openwakeword model
  - Test that feeding a mock audio chunk with wake word returns a detection event
  - Test that confidence threshold filtering works (above threshold = detected, below = ignored)
  - Test reset behavior after detection

- [ ] Task: Implement wake word detector
  - Create `src/ai_assistant/voice/wake_word.py`
  - Implement `WakeWordDetector` class wrapping openwakeword
  - Accept audio chunks, return detection events with confidence score
  - Configurable wake word and confidence threshold (default 0.7)
  - Pass all tests from previous task

- [ ] Task: Conductor - User Manual Verification 'Phase 1: Audio Capture & Wake Word Detection' (Protocol in workflow.md)

## Phase 2: Speech-to-Text

- [ ] Task: Write tests for STT engine
  - Create `tests/test_stt.py`
  - Test that `SpeechToText` initializes with a Vosk model path
  - Test that feeding audio chunks produces a transcript string
  - Test end-of-utterance detection (silence triggers final result)
  - Test error handling when model path is invalid
  - Mock `vosk` to avoid model dependency in tests

- [ ] Task: Implement STT engine
  - Create `src/ai_assistant/voice/stt.py`
  - Implement `SpeechToText` class wrapping `vosk.KaldiRecognizer`
  - Accept audio chunks, accumulate partial results, return final transcript on silence
  - Configurable model path from `config/settings.yaml`
  - Pass all tests from previous task

- [ ] Task: Conductor - User Manual Verification 'Phase 2: Speech-to-Text' (Protocol in workflow.md)

## Phase 3: Text-to-Speech

- [ ] Task: Write tests for TTS engine
  - Create `tests/test_tts.py`
  - Test that `TextToSpeech` can speak text using Edge-TTS (mock the network call)
  - Test automatic fallback to pyttsx3 when Edge-TTS fails
  - Test that TTS output produces audio data or triggers playback
  - Test empty string and long text edge cases

- [ ] Task: Implement TTS engine
  - Create `src/ai_assistant/voice/tts.py`
  - Implement `TextToSpeech` class with `speak(text)` async method
  - Online path: use `edge_tts.Communicate` to generate audio, play via sounddevice or temp file
  - Offline fallback: catch connection errors, fall back to `pyttsx3.speak()`
  - Configurable voice name in `config/settings.yaml`
  - Pass all tests from previous task

- [ ] Task: Conductor - User Manual Verification 'Phase 3: Text-to-Speech' (Protocol in workflow.md)

## Phase 4: Pipeline Orchestration & Agent Integration

- [ ] Task: Write tests for voice pipeline orchestrator
  - Create `tests/test_voice_pipeline.py`
  - Test the full pipeline flow: wake → listen → transcribe → agent → speak → listen
  - Test that events are emitted at each stage (wake_detected, listening_started, transcription_complete, speaking_started, speaking_done)
  - Test error recovery (e.g., STT fails mid-utterance, TTS fails, agent errors)
  - Mock all sub-components (AudioCapture, WakeWordDetector, SpeechToText, TextToSpeech, agent)

- [ ] Task: Implement voice pipeline orchestrator
  - Create `src/ai_assistant/voice/pipeline.py`
  - Implement `VoicePipeline` class that wires AudioCapture → WakeWordDetector → SpeechToText → LangGraph agent → TextToSpeech
  - Run as an asyncio task with start/stop controls
  - Emit events via callback or event bus for UI integration
  - Integrate with existing agent in `src/ai_assistant/agent/`
  - Pass all tests from previous task

- [ ] Task: Write tests for voice configuration
  - Create `tests/test_voice_config.py`
  - Test that voice settings are loaded from `config/settings.yaml`
  - Test default values when voice section is missing
  - Test validation of config values (e.g., threshold between 0 and 1, valid model path)

- [ ] Task: Implement voice configuration
  - Add `voice:` section to config schema in `src/ai_assistant/config/`
  - Define Pydantic model for voice settings (wake_threshold, vosk_model_path, tts_voice, input_device)
  - Wire config into VoicePipeline initialization
  - Pass all tests from previous task

- [ ] Task: Conductor - User Manual Verification 'Phase 4: Pipeline Orchestration & Agent Integration' (Protocol in workflow.md)

## Phase 5: Desktop Overlay Integration

- [ ] Task: Write tests for overlay voice events
  - Create `tests/test_overlay_voice.py`
  - Test that the desktop overlay subscribes to voice pipeline events
  - Test that UI state changes on wake_detected (show listening indicator)
  - Test that transcription text appears in chat window
  - Test that Mike's expression changes during speaking
  - Mock the tkinter overlay components

- [ ] Task: Implement overlay voice integration
  - Update `src/ai_assistant/gui/` to subscribe to VoicePipeline events
  - Show listening indicator when wake word detected
  - Display transcript in chat window when transcription completes
  - Update Mike's expression/animation state during speaking
  - Pass all tests from previous task

- [ ] Task: Wire voice pipeline startup into the main application entry point
  - Update the main app initialization to start VoicePipeline alongside the desktop overlay
  - Ensure clean shutdown of voice pipeline when app exits
  - Test that the full application starts without errors

- [ ] Task: Conductor - User Manual Verification 'Phase 5: Desktop Overlay Integration' (Protocol in workflow.md)
