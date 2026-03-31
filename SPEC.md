# Hermes Game Creator

Multi-agent swarm that turns one-line game ideas into complete, playable Python raylib games.
User provides an idea → agents expand, design, implement, and validate it → output is a runnable game.

## Why

Manually coding small games from scratch is tedious and repetitive. The design→implement→debug
cycle for a single raylib game takes hours of boilerplate (window setup, game loop, entity management,
collision detection, UI rendering). An agent swarm can parallelize this:

- **Scout** researches the idea and produces a detailed Game Design Document
- **Builders** implement each module in parallel (constants, entities, systems, UI, main)
- **Reviewer** validates all pyray API calls and cross-file imports
- **Lead** coordinates the scout→build→review pipeline
- **Coordinator** orchestrates the full run, dispatches leads, merges branches

The user's only job is typing a game idea. Everything else is autonomous.

## Design Principles

1. **One idea in, playable game out.** The user provides a natural language description.
   The swarm produces a complete `games/<slug>/` directory that runs with `python src/main.py`.
2. **Pure raylib, no external assets.** Every game uses geometric shapes and built-in
   raylib drawing primitives. No sprite sheets, no sound files, no fonts. Games are
   self-contained Python code.
3. **Scoped to 4–8 files.** Every game fits the canonical structure: `constants.py`,
   `entities.py`, `systems.py`, `ui.py`, `main.py`, `utils.py`. No sprawling codebases.
4. **Parallel by default.** Independent modules (entities, systems, UI) are built
   concurrently by separate builder agents in isolated git worktrees.
5. **Quality-gated.** No module ships without passing syntax checks and pyray API validation.
   The reviewer catches bad `rl.*` calls before merge.
6. **Git-native.** Every agent works in a worktree branch. The coordinator merges clean
   branches into main. Full audit trail via git history.
7. **Idea expansion.** Agents don't just implement the literal idea — the scout enriches
   it with game design best practices, balanced mechanics, satisfying feedback loops, and
   polish details the user didn't think of.

## Tech Stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Game framework | pyray (raylib Python bindings) | Simple, fast, no dependencies beyond `pip install raylib` |
| Language | Python 3.10+ | Accessible, fast iteration, good raylib bindings |
| Agent runtime | OpenCode v1.1.48+ | CLI-based AI coding agent, supports OpenRouter |
| LLM provider | OpenRouter | Gateway to many models, pay-per-token |
| LLM model | google/gemini-3-flash-preview | Fast, capable, cost-effective for code generation |
| Orchestration | Overstory v0.9.3+ | Multi-agent coordination, git worktrees, mail system |
| Task tracking | Seeds (auto) | JSONL-based issue tracker for agent task management |
| Knowledge base | Mulch | Persistent learnings across runs |
| VCS | Git | Worktree isolation, branch-per-agent, merge queue |
| Shell | WSL Ubuntu + tmux | Required by overstory for agent session management |

## Project Structure

```
hermes-gamedev/
├── SPEC.md                    # This file — project specification
├── CLAUDE.md                  # Agent instructions (raylib conventions, quality gates)
├── opencode.json              # OpenCode config (OpenRouter + Gemini Flash)
├── launch_game.sh             # One-command game generation entrypoint
├── .env                       # API keys (gitignored)
├── .gitignore
├── .gitattributes
├── .claude/
│   └── settings.local.json   # Claude Code settings
├── .overstory/
│   ├── config.yaml            # Overstory project config
│   ├── hooks.json             # Session/tool hooks for agent lifecycle
│   ├── agent-manifest.json    # Agent role definitions (tools, capabilities)
│   ├── agent-defs/            # Agent role prompts
│   │   ├── coordinator.md     # Top-level orchestrator
│   │   ├── lead.md            # Work stream team lead
│   │   ├── builder.md         # Code implementation specialist
│   │   ├── scout.md           # Read-only codebase researcher
│   │   ├── reviewer.md        # Code validation specialist
│   │   ├── merger.md          # Branch integration specialist
│   │   ├── orchestrator.md    # Multi-repo coordinator (unused for single-repo)
│   │   ├── monitor.md         # Watchdog sentinel
│   │   └── ov-co-creation.md  # Human-in-the-loop workflow profile
│   ├── agents/                # Runtime agent state
│   ├── worktrees/             # Git worktree directories (gitignored)
│   ├── specs/                 # Scout-produced spec files
│   ├── logs/                  # Agent session logs
│   ├── merge-queue.db         # SQLite merge queue state
│   └── sessions.db            # SQLite session tracking
├── games/                     # Generated games (one directory per game)
│   └── <slug>-<timestamp>/
│       ├── manifest.json      # Game metadata
│       ├── src/
│       │   ├── main.py        # Entry point — if __name__ == "__main__": main()
│       │   ├── constants.py   # Window size, colors, tuning values
│       │   ├── entities.py    # Game objects (player, enemies, projectiles, pickups)
│       │   ├── systems.py     # Game systems (spawning, collision, scoring, waves)
│       │   ├── ui.py          # HUD, menus, overlays
│       │   └── utils.py       # Helpers (vector math, easing, etc.)
│       ├── data/
│       │   └── config.json    # Runtime tuning (speeds, spawn rates, etc.)
│       └── docs/
│           ├── gdd.md         # Game Design Document (scout output)
│           └── systems_plan.json  # System interactions spec
└── __old/                     # Archived previous implementations
```

## Game Output Format

Every generated game follows the same canonical structure:

### `manifest.json`

```json
{
  "name": "arena-shooter",
  "description": "A top-down arena shooter with WASD movement and wave-based enemies",
  "created": "2026-03-31T12:00:00+00:00",
  "status": "complete",
  "files": ["src/main.py", "src/constants.py", "src/entities.py", "src/systems.py", "src/ui.py"]
}
```

### `src/constants.py`

All tuning values in one place. Window dimensions, colors (as `rl.Color(r,g,b,a)`), speeds,
spawn rates, scoring values. No magic numbers anywhere else.

### `src/entities.py`

Game objects as Python classes or dataclasses. Player, enemies, projectiles, pickups, particles.
Each entity has position, velocity, size, and a `draw()` method using raylib primitives.

### `src/systems.py`

Game logic systems: spawning, movement, collision detection, scoring, wave progression,
difficulty scaling. Pure functions operating on entity lists where possible.

### `src/ui.py`

HUD rendering (score, health, wave number), menus (title screen, pause, game over),
overlays (damage flash, level-up notification). Uses `rl.draw_text()` and geometric shapes.

### `src/utils.py`

Helper functions: vector math (distance, normalize, lerp), easing functions,
random position generators, rectangle intersection. Shared utilities.

### `src/main.py`

The entry point. Initializes the window, runs the game loop, ties all modules together.
Must contain `if __name__ == "__main__": main()`.

### `data/config.json`

Runtime-tunable values loaded at startup. Speeds, spawn rates, difficulty curves.
Loaded via `__file__`-based path: `os.path.join(os.path.dirname(__file__), "..", "data", "config.json")`.

### `docs/gdd.md`

Game Design Document produced by the scout agent. Contains: core concept, mechanics,
controls, feedback systems, win/lose conditions, difficulty progression, visual style.

## Agent Swarm Architecture

### Hierarchy

```
User
  └── Coordinator (1)
        ├── Lead: Game Design (1)
        │     └── Scout → writes GDD + systems_plan
        ├── Lead: Implementation (1)
        │     ├── Builder: constants.py
        │     ├── Builder: entities.py
        │     ├── Builder: systems.py
        │     ├── Builder: ui.py
        │     ├── Builder: utils.py
        │     └── Builder: main.py
        └── Lead: Validation (1)
              └── Reviewer → validates pyray API + cross-imports
```

### Agent Roles

#### Coordinator
- **Purpose:** Receives the game idea, decomposes into work streams, dispatches leads
- **Access:** Read-only. No code modification, no spec writing.
- **Dispatches:** 2-3 leads (design, implementation, validation)
- **Monitors:** Lead progress via overstory mail system
- **Merges:** Clean branches after lead signals `merge_ready`
- **Model:** gemini-3-flash-preview via OpenRouter

#### Lead (Design)
- **Purpose:** Owns the game design work stream
- **Dispatches:** Scout agent to research and produce GDD
- **Writes:** Spec files grounding the scout's findings
- **Signals:** `merge_ready` to coordinator when GDD is complete
- **Model:** gemini-3-flash-preview via OpenRouter

#### Lead (Implementation)
- **Purpose:** Owns the code implementation work stream
- **Input:** GDD and systems_plan from the design lead's branch
- **Dispatches:** 3-6 builder agents with non-overlapping file scopes
- **File scoping:** Each builder owns exactly one file (e.g., `entities.py`)
- **Signals:** `merge_ready` after all builders pass quality gates
- **Model:** gemini-3-flash-preview via OpenRouter

#### Lead (Validation)
- **Purpose:** Owns the final review work stream
- **Input:** All implementation files from merged builder branches
- **Dispatches:** Reviewer agent for cross-file validation
- **Checks:** pyray API correctness, import consistency, entry point validity
- **Signals:** `merge_ready` after reviewer reports PASS
- **Model:** gemini-3-flash-preview via OpenRouter

#### Scout
- **Purpose:** Read-only research agent that expands the user's game idea
- **Output:** `docs/gdd.md` (Game Design Document), `docs/systems_plan.json`
- **Process:**
  1. Analyze the user's idea for completeness
  2. Expand with game design best practices (feedback loops, juice, difficulty curves)
  3. Define core mechanics, controls, visual style
  4. Specify entity types, system interactions, UI elements
  5. Write structured GDD and systems plan via `ov spec write`
- **Constraints:** Read-only. Cannot modify any code files.
- **Model:** gemini-3-flash-preview via OpenRouter

#### Builder
- **Purpose:** Implementation specialist. Receives a spec and file scope, writes code.
- **Process:**
  1. Read the GDD and systems_plan
  2. Read the spec for its assigned file
  3. Implement the file using raylib conventions from CLAUDE.md
  4. Run quality gates (`python3 -m py_compile`, pyray API validation)
  5. Commit to worktree branch
  6. Send `worker_done` to parent lead
- **Constraints:** Cannot spawn sub-agents. Writes only to its assigned file scope.
- **Model:** gemini-3-flash-preview via OpenRouter

#### Reviewer
- **Purpose:** Read-only validation specialist
- **Checks:**
  1. All `rl.*` calls reference real pyray module attributes
  2. All cross-file imports resolve (e.g., `from entities import Player`)
  3. `src/main.py` has `if __name__ == "__main__": main()`
  4. No `src.` prefixed imports (flat imports only within src/)
  5. Colors use `rl.Color(r,g,b,a)` not raw tuples
  6. `rl.get_frame_time()` used for delta-time, not hardcoded values
  7. Game loop follows standard pattern (init_window → set_target_fps → loop → close_window)
- **Output:** PASS/FAIL with detailed feedback per file
- **Constraints:** Read-only. Cannot modify files.
- **Model:** gemini-3-flash-preview via OpenRouter

### Communication Flow

```
1. User runs: ./launch_game.sh "A top-down arena shooter with WASD and waves"
2. Script creates games/<slug>-<timestamp>/ skeleton, commits it
3. Script starts: ov coordinator start --attach
4. Coordinator receives objective via stdin
5. Coordinator creates seeds issues for each work stream
6. Coordinator dispatches Lead (Design) via ov mail
7. Lead (Design) spawns Scout
8. Scout explores, writes GDD + systems_plan via ov spec write
9. Scout sends worker_done to Lead (Design)
10. Lead (Design) verifies GDD, sends merge_ready to Coordinator
11. Coordinator merges design branch
12. Coordinator dispatches Lead (Implementation)
13. Lead (Implementation) reads GDD, creates per-file specs
14. Lead (Implementation) spawns Builders (constants, entities, systems, ui, utils, main)
15. Builders implement in parallel, each in own worktree
16. Each Builder runs quality gates, sends worker_done to Lead
17. Lead (Implementation) verifies all builders, sends merge_ready
18. Coordinator merges implementation branch
19. Coordinator dispatches Lead (Validation)
20. Lead (Validation) spawns Reviewer
21. Reviewer validates all pyray API calls and cross-file imports
22. Reviewer sends PASS/FAIL to Lead (Validation)
23. If PASS: Lead sends merge_ready, Coordinator closes issues
24. If FAIL: Lead dispatches fix builders for reported issues, re-reviews
25. Game complete. User can run: python games/<slug>/src/main.py
```

### Mail Types

| Type | Sender | Receiver | Purpose |
|------|--------|----------|---------|
| `dispatch` | Coordinator | Lead | Assign work stream with objective |
| `worker_done` | Builder/Scout | Lead | Report task completion |
| `merge_ready` | Lead | Coordinator | All work verified, ready to merge |
| `escalation` | Lead | Coordinator | Blocked, needs intervention |
| `status_request` | Coordinator | Lead | Progress check |
| `status_report` | Lead | Coordinator | Current state summary |
| `review_result` | Reviewer | Lead | PASS/FAIL with details |
| `nudge` | Coordinator | Any | Stall detection prompt |

## Idea Expansion Pipeline

The scout doesn't just implement what the user typed — it **expands** the idea:

### Input
```
"A top-down arena shooter with WASD and waves"
```

### Scout Expansion Process

1. **Core Loop Analysis:** What's the 10-second gameplay loop? Move, aim, shoot, dodge, collect.
2. **Mechanics Deepening:**
   - Movement: WASD with diagonal normalization, screen boundary clamping
   - Aiming: Mouse cursor tracking, rotation toward mouse
   - Shooting: Cooldown-based, projectile velocity, damage values
   - Enemies: 3+ types with distinct behaviors (charger, shooter, tank)
   - Waves: Escalating difficulty, rest periods between waves, boss every N waves
3. **Juice & Feedback:**
   - Screen shake on damage taken
   - Particle burst on enemy death
   - Score popup text that floats upward and fades
   - Health bar with color gradient (green → yellow → red)
   - Flash effect when player takes damage
4. **Progression Systems:**
   - Score multiplier for consecutive kills
   - Difficulty curve: more enemies per wave, faster spawn rates, new enemy types
   - High score tracking (in-memory, resets on restart)
5. **Win/Lose Conditions:**
   - Lose: Player health reaches 0
   - Win: Survive N waves (or endless mode with high score)
   - Game over screen with score and restart prompt
6. **Visual Style:**
   - Geometric shapes only (circles, rectangles, triangles)
   - Color palette: dark background, bright player, varied enemy colors
   - Grid or subtle background pattern for motion reference

### Output
- `docs/gdd.md`: Full Game Design Document with all above details
- `docs/systems_plan.json`: Structured entity/system interaction map

## Raylib Conventions (CRITICAL)

These rules are enforced by CLAUDE.md and validated by the reviewer agent:

### Must Do
- `import pyray as rl` — always this import convention
- `rl.Color(r, g, b, a)` for custom colors — **never raw tuples**
- `rl.get_frame_time()` for delta-time — **never hardcoded dt**
- `if __name__ == "__main__": main()` in main.py
- `__file__`-based paths for data loading
- Flat imports within `src/` (e.g., `from constants import *`)
- 60 FPS target via `rl.set_target_fps(60)`
- 800×600 or 1024×768 window size

### Must Not
- No `src.` prefixed imports
- No external game libraries (pygame, PIL, numpy)
- No external asset files (images, fonts, sounds)
- No raw color tuples — always `rl.Color()`
- No `rl.*` calls that don't exist in the real pyray module

### Standard Game Loop
```python
def main():
    rl.init_window(800, 600, "Game Title")
    rl.set_target_fps(60)

    # Initialize game state
    game = GameState()

    while not rl.window_should_close():
        dt = rl.get_frame_time()

        # Update
        game.update(dt)

        # Draw
        rl.begin_drawing()
        rl.clear_background(rl.BLACK)
        game.draw()
        rl.end_drawing()

    rl.close_window()

if __name__ == "__main__":
    main()
```

## Quality Gates

Every builder agent must pass these before signaling `worker_done`:

### Gate 1: Syntax Check
```bash
python3 -m py_compile <file>
```
All `.py` files must parse without `SyntaxError`.

### Gate 2: Pyray API Validation
```bash
python3 -c "
import ast, pyray, sys
tree = ast.parse(open(sys.argv[1]).read())
errs = [
    f'line {n.lineno} pyray.{n.attr} not found'
    for n in ast.walk(tree)
    if isinstance(n, ast.Attribute)
    and isinstance(n.value, ast.Name)
    and n.value.id in ('rl', 'pyray')
    and n.attr not in dir(pyray)
]
print(chr(10).join(errs) or 'OK')
sys.exit(1 if errs else 0)
" <file>
```
All `rl.<attr>` references must exist in the real pyray module.

### Gate 3: Entry Point Check
```bash
python3 -c "
import ast, sys
tree = ast.parse(open(sys.argv[1]).read())
has_main = any(
    isinstance(n, ast.If)
    and isinstance(n.test, ast.Compare)
    and any(isinstance(c, ast.Constant) and c.value == '__main__' for c in [n.test.left] + n.test.comparators)
    for n in ast.walk(tree)
)
print('OK' if has_main else 'FAIL: missing if __name__ == \"__main__\"')
sys.exit(0 if has_main else 1)
" src/main.py
```

### Gate 4: Import Consistency (Reviewer)
Cross-file import validation — every `from <module> import <name>` must resolve
to an actual definition in the referenced file.

## Configuration

### `.overstory/config.yaml`

Key settings for the agent swarm:

```yaml
project:
  name: raylib-gamedev
  canonicalBranch: main
  qualityGates:
    - name: Syntax
      command: python3 -m py_compile src/main.py
    - name: PyrayAPI
      command: <AST-based pyray attribute validation>

agents:
  maxConcurrent: 5        # Max simultaneous agents
  maxAgentsPerLead: 3     # Builders per lead
  staggerDelayMs: 3000    # Delay between agent launches

models:                   # All roles use the same model
  coordinator: openrouter/google/gemini-3-flash-preview
  lead: openrouter/google/gemini-3-flash-preview
  builder: openrouter/google/gemini-3-flash-preview
  scout: openrouter/google/gemini-3-flash-preview
  reviewer: openrouter/google/gemini-3-flash-preview

runtime:
  default: opencode       # OpenCode as agent runtime (not Claude Code)
  shellInitDelayMs: 2000
```

### `opencode.json`

OpenCode project config for OpenRouter integration:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {}
  },
  "model": "openrouter/google/gemini-3-flash-preview",
  "small_model": "openrouter/google/gemini-3-flash-preview",
  "disabled_providers": ["openai", "anthropic", "gemini", "groq"],
  "instructions": ["CLAUDE.md"]
}
```

API key auto-detected from `OPENROUTER_API_KEY` environment variable.

### `.env`

```
OPENROUTER_API_KEY=<your-key>
```

## User Workflow

### Generate a Game

```bash
# From WSL terminal in project root
./launch_game.sh "A snake game with growing difficulty and power-ups"
```

This:
1. Creates `games/a-snake-game-20260331-120000/` skeleton
2. Commits the skeleton to git
3. Starts the overstory coordinator in an attached tmux session
4. Agents autonomously design, build, and validate the game
5. Final output: a playable game in the `games/` directory

### Run the Game

```bash
cd games/a-snake-game-20260331-120000
python3 src/main.py
```

### Monitor Progress

```bash
# View the tmux dashboard
ov dashboard

# Check agent status
ov status

# Read agent mail
ov mail list
```

## What This Project Does NOT Do

- **No 3D games.** 2D only, using raylib's 2D drawing primitives.
- **No asset pipeline.** No sprites, no audio, no fonts. Pure geometric rendering.
- **No multiplayer.** Single-player games only.
- **No save/load.** Games are session-based. High scores are in-memory.
- **No packaging/distribution.** Games run from source with `python3 src/main.py`.
- **No web deployment.** Desktop only, requires local Python + raylib.
- **No manual editing required.** The output should be playable without human code fixes.
  (If quality gates pass, the game runs.)

## Estimated Agent Cost Per Game

| Role | Count | Sessions | Approx Tokens |
|------|-------|----------|---------------|
| Coordinator | 1 | 1 | ~5K |
| Lead (Design) | 1 | 1 | ~5K |
| Scout | 1 | 1 | ~10K |
| Lead (Implementation) | 1 | 1 | ~8K |
| Builders | 4-6 | 4-6 | ~8K each |
| Lead (Validation) | 1 | 1 | ~5K |
| Reviewer | 1 | 1 | ~10K |
| **Total** | **10-14** | **10-14** | **~75-95K** |

At Gemini Flash pricing (~$0.10/M input, ~$0.40/M output via OpenRouter),
a typical game generation run costs approximately **$0.05–0.15**.

## Future Enhancements

Explicitly out of scope for v1, but planned:

- **Game templates.** Pre-defined molecule templates for common genres (platformer, shooter, puzzle)
- **Iterative refinement.** "Make the enemies faster" → agents modify existing game
- **Replay learning.** Mulch captures what worked/failed across runs for improving future games
- **Batch generation.** Generate multiple game variants from one idea
- **Automated playtesting.** Headless game execution with heuristic scoring
