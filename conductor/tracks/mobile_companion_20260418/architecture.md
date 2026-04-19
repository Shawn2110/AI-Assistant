# Architecture: Mobile Companion

**Track:** `mobile_companion_20260418`
**Date:** 2026-04-18

## System Overview

```
┌─────────────────────────────────────────┐        ┌──────────────────────────────────┐
│            Android Phone                │        │   Desktop / Self-Hosted Host     │
│  ┌───────────────────────────────────┐  │        │                                  │
│  │     MAUI Companion App            │  │        │  ┌────────────────────────────┐  │
│  │                                   │  │        │  │  FastAPI Backend           │  │
│  │  UI (Blazor Hybrid)               │◄─┼──TLS──►│  │  (src/server/)             │  │
│  │  Pairing / Password / Settings    │  │ Signed │  │                            │  │
│  │                                   │  │  RPC   │  │  /mobile/pair              │  │
│  │  Phone Integration Layer          │  │        │  │  /mobile/cmd               │  │
│  │  ├─ AppLauncher (PackageManager)  │  │        │  │  /mobile/events (WS)       │  │
│  │  ├─ SMS Observer (SmsManager)     │  │        │  └────────┬───────────────────┘  │
│  │  ├─ CallScreeningService          │  │        │           │                      │
│  │  └─ NotificationListener (Ph.3)   │  │        │  ┌────────▼───────────────────┐  │
│  │                                   │  │        │  │  LangGraph Agent           │  │
│  │  Security Vault                   │  │        │  │  (src/ai/)                 │  │
│  │  ├─ Argon2id(master_password)     │  │        │  │                            │  │
│  │  ├─ Ed25519 keypair               │  │        │  │  Tools: launch_app,        │  │
│  │  ├─ Permission allowlist          │  │        │  │   send_sms, screen_call,   │  │
│  │  └─ EncryptedSharedPreferences    │  │        │  │   read_voicemail           │  │
│  └───────────────────────────────────┘  │        │  └────────┬───────────────────┘  │
│                                         │        │           │                      │
└─────────────────────────────────────────┘        │  ┌────────▼───────────────────┐  │
                                                   │  │  Voice Pipeline            │  │
                                                   │  │  (src/voice/)              │  │
                                                   │  │  STT / TTS reused for VM   │  │
                                                   │  └────────────────────────────┘  │
                                                   └──────────────────────────────────┘
```

## Components

### Mobile App (MAUI, .NET 9)

| Component             | Responsibility                                                                 |
|-----------------------|---------------------------------------------------------------------------------|
| `PairingPage`         | Scan QR from backend, exchange Ed25519 public keys, persist backend base URL.  |
| `PasswordVault`       | Argon2id hash of master password stored in `EncryptedSharedPreferences`.       |
| `PermissionStore`     | SQLite table of `(capability_key, granted_at, revoked_at)`. Encrypted at rest. |
| `AppLauncher`         | Wraps `PackageManager` + `Context.startActivity` for intent launches.          |
| `SmsBridge`           | `BroadcastReceiver` for inbound, `SmsManager` for outbound.                    |
| `CallScreeningImpl`   | Android `CallScreeningService` subclass. Routes calls per user rule set.       |
| `RpcClient`           | Signed HTTP + WebSocket client. All outbound requests are Ed25519-signed.      |
| `CommandDispatcher`   | Receives backend commands, enforces allowlist, prompts for password on first use. |

### Backend (existing FastAPI, new module `src/mobile/`)

| Component            | Responsibility                                                                        |
|----------------------|----------------------------------------------------------------------------------------|
| `mobile/pairing.py`  | Generates one-time QR payload, validates phone's public key, issues session token.    |
| `mobile/transport.py`| Signature verification middleware, enforces replay protection (nonce + timestamp).    |
| `mobile/tools.py`    | LangGraph tools that RPC into the paired phone. Returns pending state if phone offline.|
| `mobile/events.py`   | WebSocket hub — phone pushes inbound SMS/call events, backend fans out to the agent. |
| `mobile/vault.py`    | Stores only the phone's public key + allowlist shadow copy for offline UX (read-only).|

## Data Model

### Mobile SQLite (`companion.db`)

```sql
CREATE TABLE permissions (
  capability_key TEXT PRIMARY KEY,   -- e.g. "launch_app:com.spotify.music", "send_sms"
  granted_at     INTEGER NOT NULL,
  revoked_at     INTEGER,
  note           TEXT
);

CREATE TABLE pairings (
  backend_url         TEXT PRIMARY KEY,
  backend_public_key  BLOB NOT NULL,
  paired_at           INTEGER NOT NULL,
  last_seen_at        INTEGER
);

CREATE TABLE call_rules (
  match_rule  TEXT PRIMARY KEY,    -- "unknown", "contact:<id>", "number:<E.164>"
  action      TEXT NOT NULL,       -- "ignore" | "screen" | "answer"
  updated_at  INTEGER NOT NULL
);
```

### Backend (extends `src/core/config.py`)

- `config/mobile_pairings.json` — list of paired devices, their public keys, human label, and last-seen timestamp.
- No SMS/voicemail content persisted server-side by default; only transient agent context.

## Security Model

### Password

- Master password is entered on the phone only. It is *never* transmitted.
- Hash: **Argon2id** (time=3, memory=64 MiB, parallelism=2).
- Three wrong attempts → 60 s backoff, doubling per subsequent batch of three.
- Reset requires reinstall (acceptable tradeoff for a single-user personal tool).

### Pairing

1. User runs `assistant --server`. Backend prints a QR containing `{server_url, server_pubkey, nonce}`.
2. Phone scans, generates Ed25519 keypair, sends `{phone_pubkey, nonce, hmac}` over TLS.
3. Backend verifies and stores the phone's public key.
4. All subsequent requests carry header `X-Sig: ed25519(base64(body || timestamp || nonce))`. Nonces live 60 s.

### Authorization Flow (First-Time App Launch)

```
Agent decides → launch_app("Spotify")
  └─ backend RPC → phone CommandDispatcher
       ├─ check PermissionStore for "launch_app:com.spotify.music"
       │    ├─ found & not revoked → execute
       │    └─ missing              → prompt password
       │          ├─ correct        → record grant, execute, ack backend
       │          └─ wrong          → deny, increment lockout counter
       └─ ack sent back to agent as tool result ("launched" | "denied" | "pending_user")
```

### Threat Model & Mitigations

| Threat                                          | Mitigation                                           |
|-------------------------------------------------|------------------------------------------------------|
| Stolen ngrok URL                                | Signed requests — URL alone is not enough.           |
| Compromised backend (attacker runs Mike code)   | Phone still enforces allowlist + password locally.   |
| Replay attack on captured request               | Nonce + timestamp window (60 s).                     |
| Lost phone                                      | Re-pair from backend wipes old device's key.         |
| Malicious app on phone invoking our RPC         | Companion exposes no public services; backend-initiated only. |

## Platform Notes

### Android (MVP)

- Min API: 29 (Android 10) for `CallScreeningService`.
- Runtime permissions: `READ_SMS`, `SEND_SMS`, `RECEIVE_SMS`, `ANSWER_PHONE_CALLS`, `READ_PHONE_STATE`, `QUERY_ALL_PACKAGES`, `POST_NOTIFICATIONS`.
- `QUERY_ALL_PACKAGES` triggers Play Store review — acceptable since we're side-loading.
- Accessibility Service is *not* required for MVP. If added later for WhatsApp Direct Reply, it's an opt-in capability.

### iOS (Phase 4, stretch)

- App launch: not possible without URL schemes the target app declares. Fallback: Siri Shortcuts list.
- SMS: read-only access via Shortcuts; no programmatic send.
- Calls: CallKit for declining/VoIP only; no PSTN answer-by-AI.
- Expect iOS feature set to be ~30% of Android. Track it as a separate phase.

## Code Layout

```
src/mobile/                     # NEW backend module
  __init__.py
  pairing.py
  transport.py
  events.py
  tools.py                      # LangGraph tools that RPC to phone
  vault.py

mobile/                         # NEW MAUI app (.NET 9)
  MikeCompanion.sln
  MikeCompanion/
    Platforms/Android/
      AppLauncherService.cs
      SmsReceiver.cs
      MikeCallScreeningService.cs
    Services/
      PasswordVault.cs
      PermissionStore.cs
      RpcClient.cs
      CommandDispatcher.cs
    Pages/
      PairingPage.xaml
      PermissionsPage.xaml
      SettingsPage.xaml
    MauiProgram.cs
```

## Deployment

- Backend: existing `assistant --server` + ngrok tunnel. No new infra.
- Mobile: side-loaded APK at first; optional internal Play Store listing later.
- CI: add GitHub Actions job `android-ci` that runs `dotnet build -t:Package` and uploads the APK as a release artifact.
