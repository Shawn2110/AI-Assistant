# Plan: Mobile Companion

**Track:** `mobile_companion_20260418`
**Date:** 2026-04-18
**Methodology:** Conductor TDD — each task writes tests first, then implementation.

## Phase 0: Scaffolding & Pairing Protocol

- [ ] Task: Create `src/mobile/` Python package with `__init__.py`, `pairing.py`, `transport.py` stubs
- [ ] Task: Design pairing message schema (`PairRequest`, `PairResponse`) with Pydantic
- [ ] Task: Write tests for pairing — QR payload generation, key-exchange roundtrip, nonce replay rejection
- [ ] Task: Implement `/mobile/pair` FastAPI endpoint and pass tests
- [ ] Task: Write tests for request-signing middleware — valid Ed25519 sig passes, bad sig 401, stale timestamp 401
- [ ] Task: Implement `src/mobile/transport.py` middleware and pass tests
- [ ] Task: Scaffold MAUI solution `mobile/MikeCompanion/` with MAUI Blazor Hybrid template
- [ ] Task: Add `PairingPage.xaml` that scans a QR via `ZXing.Net.Maui`
- [ ] Task: Implement phone-side Ed25519 keygen + signed RPC client (`RpcClient.cs`)
- [ ] Checkpoint: User Manual Verification — pair phone with backend end-to-end

## Phase 1: Password Vault & Permission Store

- [ ] Task: Write tests for `PasswordVault` — Argon2id hash, verify, lockout after 3 failures, exponential backoff
- [ ] Task: Implement `PasswordVault.cs` using `Konscious.Security.Cryptography.Argon2`
- [ ] Task: Write tests for `PermissionStore` — grant, revoke, query, SQLite encryption at rest
- [ ] Task: Implement `PermissionStore.cs` with SQLite + SQLCipher
- [ ] Task: Build first-run UX flow — "Set your master password" screen
- [ ] Task: Build permissions management screen — list granted capabilities, allow revoke
- [ ] Checkpoint: User Manual Verification — set password, grant a fake capability, revoke it

## Phase 2: App Launch

- [ ] Task: Write tests for `AppLauncher` — enumerate packages (mocked), resolve by label, launch by package_id
- [ ] Task: Implement `AppLauncher.cs` wrapping `PackageManager`
- [ ] Task: Write backend tests for `launch_app` tool — RPC to phone, handle all four statuses
- [ ] Task: Implement `launch_app` in `src/mobile/tools.py` and register with `get_all_tools()`
- [ ] Task: Implement `CommandDispatcher` permission check + password prompt flow on the phone
- [ ] Task: Wire end-to-end — agent says `launch_app("Spotify")`, phone prompts, opens Spotify
- [ ] Checkpoint: User Manual Verification — "Hey Mike, open Spotify" launches the app on first approval

## Phase 3: SMS In & Out

- [ ] Task: Write tests for `SmsBridge` — outbound send, inbound observer parses `SmsMessage`
- [ ] Task: Implement `SmsBridge.cs` (outbound via `SmsManager`, inbound via `BroadcastReceiver`)
- [ ] Task: Request runtime SMS permissions with rationale screens
- [ ] Task: Write backend tests for `send_sms` and `reply_to_incoming_sms` tools (confirm gate, recipient resolution)
- [ ] Task: Implement backend tools + event bus entry for `sms_received`
- [ ] Task: Update agent system prompt for mobile mode (see `agent.md`)
- [ ] Task: Write prompt-regression tests for the three agent scripts in `agent.md`
- [ ] Checkpoint: User Manual Verification — inbound SMS surfaces in voice mode, reply flow completes

## Phase 4: Call Screening & Voicemail

- [ ] Task: Write tests for `CallScreeningImpl` — route rules (contact pass-through, unknown → screen), decline, voicemail
- [ ] Task: Implement `MikeCallScreeningService.cs` extending `CallScreeningService`
- [ ] Task: Build call-rule configuration UI
- [ ] Task: Integrate voicemail audio pipe → existing `src/voice/stt.py` for transcription
- [ ] Task: Write backend tests for `screen_call` and `read_voicemail` tools
- [ ] Task: Implement tools + event bus entries for `call_ringing`, `voicemail_ready`
- [ ] Task: Add call-summary prompt to agent (summarize transcript in 1-2 sentences)
- [ ] Checkpoint: User Manual Verification — screen an unknown call, listen to AI-summarized voicemail

## Phase 5: Hardening & Packaging

- [ ] Task: Adversarial test pass — replay attacks, bad signatures, revoked keys, wrong password lockout
- [ ] Task: Add offline behavior — queue events, flush on reconnect, surface `phone_offline` to agent
- [ ] Task: Add metrics — launch latency p50/p95, SMS round-trip, phone-offline duration
- [ ] Task: Package APK via GitHub Actions (`android-ci`) with release artifact upload
- [ ] Task: Write pairing + setup guide in `docs/mobile_companion.md`
- [ ] Task: Update `README.md` with mobile companion section once stable
- [ ] Checkpoint: User Manual Verification — fresh-install walkthrough on a clean device completes in <10 minutes

## Phase 6 (Stretch): WhatsApp / Notification Reply

- [ ] Task: Prototype `NotificationListenerService` that detects WhatsApp messages and uses `Notification.Action.RemoteInput` to reply
- [ ] Task: Gate via a new `respond_notifications` capability in the allowlist
- [ ] Task: Extend agent tool `reply_to_notification(thread_id, body, confirm=True)`
- [ ] Checkpoint: User Manual Verification — reply to a WhatsApp message by voice

## Phase 7 (Stretch): iOS Parity

- [ ] Task: Spike on Siri Shortcuts for app launch; document what's achievable
- [ ] Task: Implement iOS `CallKit` declination / VoIP path if feasible
- [ ] Task: Decide shippable iOS subset, or deprecate iOS track

## Dependencies

- **Phase 0** must complete before any other phase — nothing works without pairing + signed transport.
- **Phase 1** must complete before Phase 2 — no capability executes without the password gate.
- Phase 2 and Phase 3 can run in parallel once Phase 1 ships.
- Phase 4 depends on Phase 3 (shared event-bus plumbing).
- Phase 5 is cross-cutting; start after Phase 4 has a working happy path.

## Risks

| Risk                                                              | Mitigation                                                            |
|-------------------------------------------------------------------|-----------------------------------------------------------------------|
| Play Store rejects `QUERY_ALL_PACKAGES` for a side-loaded app     | Non-issue for side-load; defer Play Store listing                    |
| `CallScreeningService` API behaves differently across OEMs        | Test on Pixel, Samsung, OnePlus; document quirks                     |
| User loses phone with paired state                                | Backend-side "revoke device" button + forced re-pair                 |
| ngrok free-tier URL rotates, breaking the paired backend_url      | Support DNS-based backend addresses; auto-reconnect with fallback    |
| MAUI Android version drift breaks CI                              | Pin .NET SDK + MAUI workload versions in `global.json`               |

## Definition of Done

- All phases 0–5 complete and checkpointed.
- Fresh device can pair + approve Spotify launch in under 90 s.
- Three adversarial scenarios (bad sig, replay, wrong password) all fail closed.
- `docs/mobile_companion.md` describes setup end-to-end.
- Track archived to `conductor/archive/mobile_companion_20260418/`.
