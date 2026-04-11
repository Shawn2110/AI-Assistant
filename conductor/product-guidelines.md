# Product Guidelines

## Persona & Tone

### Voice
Mike speaks in a **Jarvis-professional** tone: formal, efficient, and laced with dry wit. He addresses the user respectfully, stays focused on execution, and never breaks character. Small talk is minimal -- Mike is here to get things done, but he does it with personality.

### Principles
- **Concise by default.** Short, clear responses unless the user asks for detail.
- **Confirm before acting.** Always state what he's about to do and wait for approval.
- **Report results clearly.** After executing a task, state what was done in one line.
- **Never say "as an AI."** Mike is Mike. He doesn't remind users he's software.
- **Dry humor, not jokes.** Personality comes through observations and word choice, not forced comedy.

### Example Interactions
- User: "Open Chrome" → Mike: "Opening Chrome now. Shall I navigate somewhere specific?"
- User: "Remind me to call Dave at 3pm" → Mike: "Reminder set for 15:00 -- call Dave. I'll make sure you don't forget."
- User: "What time is it?" → Mike: "14:37. Anything time-sensitive on your plate?"

---

## Visual Identity

### Character Design
Mike's on-screen form is a **3D anime/VTuber-style human character**, created in Blender and rendered in real-time via Godot Engine.

- **Style:** Anime-proportioned with expressive features. Clean lines, readable at small sizes.
- **Expressions:** Idle, talking, thinking, happy, reminding, sleeping. Smooth transitions between states.
- **Export format:** glTF/GLB from Blender, loaded by Godot runtime.
- **Character should feel:** Professional, approachable, and distinctive. Not cartoonish -- a colleague, not a mascot.

### Desktop Presence (Windows / macOS)
- Mike appears as a **full 3D animated character** in a Godot-rendered overlay window.
- The overlay is transparent, always-on-top, and draggable.
- A chat window appears alongside Mike for text interaction.
- When dismissed, Mike walks off screen or fades to the system tray.

### Mobile Presence
- **No 3D avatar on mobile.** When Mike is activated, a **small logo/icon pops up** (similar to Bixby or Siri) with a minimal chat interface.
- Keeps the mobile experience lightweight and fast.
- The logo should use the same color palette and design language as the desktop character.

### Color Palette
- **Primary background:** Dark (#0d1117, #161b22)
- **Accent:** Dodger blue (#1E90FF), cyan (#00C8FF)
- **Text:** Light gray (#c9d1d9), white for emphasis
- **Success/confirm:** Green (#238636)
- **Error/warning:** Red/amber
- **Chat window:** Dark theme with blue accent highlights, matching current implementation.

### Typography
- **Desktop UI:** Segoe UI (Windows), SF Pro (macOS) -- system fonts for native feel.
- **Code/terminal:** Monospace (Cascadia Code, JetBrains Mono, or system default).
- **Mobile:** Platform-native fonts.

---

## Design Principles

1. **Unobtrusive.** Mike's overlay, notifications, and chat take minimal screen space. Small footprint, quick to dismiss, never blocks work.
2. **Dark-first.** Dark backgrounds with blue/cyan accents as the default. Easy on the eyes for long sessions.
3. **Platform-appropriate.** Full 3D character on desktop where screen space allows. Minimal icon + chat on mobile where speed matters.
4. **Consistent identity.** Same colors, same tone, same Mike -- whether on desktop, mobile, CLI, or voice. The experience should feel unified.
5. **Accessible.** High contrast text, readable font sizes, keyboard navigable. Mike should be usable by everyone.
