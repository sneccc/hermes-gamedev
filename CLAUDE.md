# Raylib Game Development Project

This project uses overstory multi-agent orchestration to create Python raylib games.

## Tech Stack
- **Language:** Python 3.10+
- **Graphics:** raylib via `pyray` (`pip install raylib`)
- **Import convention:** `import pyray as rl`
- **No other graphics/game libraries** (no pygame, PIL, numpy, etc.)

## Project Structure
Generated games live under `games/<slug>-<timestamp>/`:
```
games/<slug>/
├── src/
│   ├── main.py          # Entry point — if __name__ == "__main__": main()
│   ├── constants.py     # Window size, colors, tuning values
│   ├── entities.py      # Game objects (player, enemies, projectiles, pickups)
│   ├── systems.py       # Game systems (spawning, collision, scoring, waves)
│   ├── ui.py            # HUD, menus, overlays
│   └── utils.py         # Helpers (vector math, easing, etc.)
├── data/
│   └── config.json      # Runtime tuning (speeds, spawn rates, etc.)
├── docs/
│   ├── gdd.md           # Game Design Document
│   └── systems_plan.json # System interactions spec
└── manifest.json        # File listing + metadata
```

## Raylib Conventions (CRITICAL)
- Always use `rl.Color(r, g, b, a)` for custom colors — **never raw tuples**
- Standard game loop:
  ```python
  rl.init_window(width, height, title)
  rl.set_target_fps(60)
  while not rl.window_should_close():
      # update logic
      rl.begin_drawing()
      rl.clear_background(rl.BLACK)
      # draw calls
      rl.end_drawing()
  rl.close_window()
  ```
- Entry point: `if __name__ == "__main__": main()`
- Use `__file__`-based paths for loading data: `os.path.join(os.path.dirname(__file__), "..", "data", "config.json")`
- Do NOT use `src.` module imports — use relative imports or flat imports within the src/ directory
- All pyray attribute references (`rl.xxx`) must exist in the real pyray module's API
- Use `rl.get_frame_time()` for delta-time, not hardcoded dt values

## Quality Gates
Before reporting work as done:
1. All `.py` files must parse without SyntaxError (`python3 -m py_compile <file>`)
2. All `rl.<attr>` calls must reference real pyray attributes
3. `src/main.py` must be the runnable entry point

## Game Design Principles
- Scope to what fits in 4–8 Python files
- Every game must be playable and have: controls, feedback, win/lose condition, score
- Use geometric shapes and built-in raylib drawing (no external assets)
- Target 60 FPS, 800×600 or 1024×768 window

<!-- mulch:start -->
## Project Expertise (Mulch)
<!-- mulch-onboard-v:1 -->

This project uses [Mulch](https://github.com/jayminwest/mulch) for structured expertise management.

**At the start of every session**, run:
```bash
mulch prime
```

This injects project-specific conventions, patterns, decisions, and other learnings into your context.
Use `mulch prime --files src/foo.ts` to load only records relevant to specific files.

**Before completing your task**, review your work for insights worth preserving — conventions discovered,
patterns applied, failures encountered, or decisions made — and record them:
```bash
mulch record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
```

Link evidence when available: `--evidence-commit <sha>`, `--evidence-bead <id>`

Run `mulch status` to check domain health and entry counts.
Run `mulch --help` for full usage.
Mulch write commands use file locking and atomic writes — multiple agents can safely record to the same domain concurrently.

### Before You Finish

1. Discover what to record:
   ```bash
   mulch learn
   ```
2. Store insights from this work session:
   ```bash
   mulch record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
   ```
3. Validate and commit:
   ```bash
   mulch sync
   ```
<!-- mulch:end -->

<!-- seeds:start -->
## Issue Tracking (Seeds)
<!-- seeds-onboard-v:1 -->

This project uses [Seeds](https://github.com/jayminwest/seeds) for git-native issue tracking.

**At the start of every session**, run:
```
sd prime
```

This injects session context: rules, command reference, and workflows.

**Quick reference:**
- `sd ready` — Find unblocked work
- `sd create --title "..." --type task --priority 2` — Create issue
- `sd update <id> --status in_progress` — Claim work
- `sd close <id>` — Complete work
- `sd dep add <id> <depends-on>` — Add dependency between issues
- `sd sync` — Sync with git (run before pushing)

### Before You Finish
1. Close completed issues: `sd close <id>`
2. File issues for remaining work: `sd create --title "..."`
3. Sync and push: `sd sync && git push`
<!-- seeds:end -->
