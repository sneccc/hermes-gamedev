"""
Swarms AI Gamedev Team — Python Raylib Games
Uses AgentRearrange for: GameDesigner -> RaylibDeveloper -> CodeReviewer
Runs DebugAgent only when static validation finds pyray issues.

Workspace layout (rooted at WORKSPACE_DIR, default: agent_workspace/):
    agent_workspace/
    ├── agents/
    │   ├── GameDesigner-<uuid>/       ← autosaved agent state + config
    │   ├── RaylibDeveloper-<uuid>/
    │   ├── CodeReviewer-<uuid>/
    │   └── DebugAgent-<uuid>/
    └── games/
            └── <slug>-<timestamp>/
                    ├── game.py                ← final runnable game
                    └── gdd.txt                ← Game Design Document
            └── trace.json             ← machine-readable swarm trace
"""

import argparse
import json
import os
import re
import ast
import datetime
import shutil
import sys
from dotenv import load_dotenv
from swarms import Agent, AgentRearrange
import pyray as _rl  # used only for dir() — no window opened

load_dotenv()

MODEL = "openrouter/google/gemini-3-flash-preview"

# Root workspace — driven by WORKSPACE_DIR env var (swarms standard)
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "agent_workspace")
DEFAULT_TASK = (
    "Create a simple Snake game: the snake grows when it eats food, "
    "the game ends when the snake hits a wall or itself, "
    "score is shown on screen, difficulty increases with length."
)

# All real pyray attribute names — used for static validation (no window needed)
_PYRAY_ATTRS = set(dir(_rl))

# ── Debug tool (given to DebugAgent) ──────────────────────────────────────────

def check_game_code(code: str) -> str:
    """
    Performs a headless static analysis of pyray game code — no window is opened.

    Step 1: Parse the source for SyntaxErrors.
    Step 2: Walk the AST and find every `rl.<attr>` (or `pyray.<attr>`) call;
            validate each attribute against the real pyray module's dir().

    Args:
        code (str): Complete Python source code to check.

    Returns:
        str: Newline-separated list of errors found, or "No errors found." if clean.
    """
    # Step 1 — syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"

    # Step 2 — discover which local names refer to pyray
    rl_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pyray":
                    rl_names.add(alias.asname or "pyray")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "pyray":
                for alias in node.names:
                    rl_names.add(alias.asname or alias.name)

    if not rl_names:
        return "Warning: no 'import pyray' found in code."

    # Step 3 — check every rl.<attr> against the real API
    errors: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in rl_names
            and node.attr not in _PYRAY_ATTRS
        ):
            errors.append(
                f"Line {node.lineno}: pyray has no attribute '{node.attr}' "
                f"— did you mean one of: "
                + ", ".join(
                    a for a in _PYRAY_ATTRS
                    if node.attr.replace("_", "") in a.replace("_", "")
                )[:120]
            )

    return "\n".join(errors) if errors else "No errors found."

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_game_slug(task: str) -> str:
    """Turn the task prompt into a filesystem-safe short slug."""
    words = re.sub(r"[^a-zA-Z0-9 ]", "", task.lower()).split()
    return "-".join(words[:4]) or "game"


def make_game_dir(slug: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    game_dir = os.path.join(WORKSPACE_DIR, "games", f"{slug}-{ts}")
    os.makedirs(game_dir, exist_ok=True)
    return game_dir


def clean_workspace_dir() -> None:
    """Remove the generated workspace tree for a clean run."""
    if os.path.isdir(WORKSPACE_DIR):
        for name in os.listdir(WORKSPACE_DIR):
            path = os.path.join(WORKSPACE_DIR, name)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except PermissionError:
                if os.path.basename(path).lower() == "error.txt":
                    try:
                        with open(path, "w", encoding="utf-8") as handle:
                            handle.write("")
                    except OSError:
                        pass
                    continue
                raise
    os.makedirs(WORKSPACE_DIR, exist_ok=True)


def get_final_agent_output(agent: Agent, fallback: str = "") -> str:
    """Get the final agent message from short memory using swarms' own API."""
    if hasattr(agent, "short_memory") and agent.short_memory is not None:
        getter = getattr(
            agent.short_memory, "get_final_message_content", None
        )
        if callable(getter):
            content = getter()
            if isinstance(content, str) and content.strip():
                return content.strip()

    return fallback.strip()


def is_valid_python_source(text: str) -> bool:
    """Return True when text parses as valid Python source."""
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    return True


def extract_python_code(text: str) -> str:
    """Pull valid Python source out of agent output."""
    text = (text or "").strip()
    blocks = [
        block.strip()
        for block in re.findall(
            r"```python\s*(.*?)```", text, re.DOTALL | re.IGNORECASE
        )
    ]

    for block in reversed(blocks):
        if is_valid_python_source(block):
            return block

    if text.startswith(("\"", "'")) and "\\n" in text:
        try:
            decoded = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            decoded = None

        if isinstance(decoded, str):
            decoded = decoded.strip()
            if is_valid_python_source(decoded):
                return decoded

    if is_valid_python_source(text):
        return text

    return blocks[-1] if blocks else text


def enable_trace_metadata(agent: Agent) -> None:
    """Ensure runtime agent messages include timestamps and message IDs."""
    if hasattr(agent, "short_memory") and agent.short_memory is not None:
        agent.short_memory.time_enabled = True
        agent.short_memory.message_id_on = True


def get_conversation_trace(conversation: object) -> list[dict]:
    """Return machine-readable trace data from a Swarms Conversation."""
    if conversation is None:
        return []

    to_dict = getattr(conversation, "to_dict", None)
    if callable(to_dict):
        trace = to_dict()
        if isinstance(trace, list):
            return trace

    history = getattr(conversation, "conversation_history", [])
    return history if isinstance(history, list) else []


def build_trace(
    task: str,
    swarm_flow: str,
    final_agent_name: str,
    validation_result: str,
    team_conversation: object,
    agents: dict[str, Agent],
) -> dict:
    """Build structured trace output separate from the generated payload files."""
    return {
        "generated_at": datetime.datetime.now().isoformat(),
        "task": task,
        "flow": swarm_flow,
        "final_agent": final_agent_name,
        "final_validation": validation_result,
        "team_trace": get_conversation_trace(team_conversation),
        "agent_traces": {
            name: get_conversation_trace(
                getattr(agent, "short_memory", None)
            )
            for name, agent in agents.items()
        },
    }


def save_outputs(code_output: str, gdd: str, game_dir: str) -> str:
    """Save gdd.txt and game.py into game_dir, return path to game.py."""
    gdd_path = os.path.join(game_dir, "gdd.txt")
    with open(gdd_path, "w", encoding="utf-8") as f:
        f.write(gdd)

    code = extract_python_code(code_output)
    game_path = os.path.join(game_dir, "game.py")
    with open(game_path, "w", encoding="utf-8") as f:
        f.write(code)

    return game_path


def save_trace(trace_data: dict, game_dir: str) -> str:
    """Save structured swarm trace alongside the generated payload files."""
    trace_path = os.path.join(game_dir, "trace.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, indent=2, default=str)

    return trace_path


# ── Agents ────────────────────────────────────────────────────────────────────

game_designer = Agent(
    agent_name="GameDesigner",
    agent_description="Designs Python raylib games and produces a Game Design Document",
    system_prompt="""You are an expert game designer specialising in small, single-file Python raylib games.

Given a game concept or request, output a detailed, implementation-ready Game Design Document in markdown.

Depth is more important than brevity. Fill the document with rich detail, concrete mechanics, numeric starting values where useful, and explicit implementation notes.
Assume the developer should be able to build the game directly from this GDD with minimal guesswork.

Required sections:
1. Title, genre, and player fantasy
2. Design pillars: 3-5 short bullets that define what the game should feel like
3. Core loop: what the player does moment to moment and over a 30-second stretch
4. Controls: full input mapping, contextual actions, and any restart/pause input
5. Player kit: movement, attacks, abilities, cooldowns, stats, and fail states
6. World and entities: player, enemies, pickups, projectiles, hazards, goals; for each include purpose, behaviour, and interactions
7. Rules and systems: spawning, collisions, health, score, timers, waves, progression, and resource loops
8. UI and screen layout: HUD, feedback, important readouts, win/lose messaging
9. Visual direction: shapes, colours, effects, readability rules, and how to stay asset-free
10. Difficulty and tuning: starting values, escalation rules, pacing, and suggested numeric ranges where useful
11. Technical notes: implementation constraints, edge cases, and tricky logic to watch for

Rich-detail rules:
- For controls, include every input and what it does in each state.
- For the player kit, include movement feel, combat options, cooldowns, invulnerability, and failure states.
- For entities, describe purpose, spawn behaviour, attack pattern, movement style, collision behaviour, and scoring impact.
- For systems, include concrete rules, timers, thresholds, and how systems interact.
- For UI, include exact on-screen information and when overlays appear.
- For difficulty, include an early/mid/late game pacing breakdown and at least a few suggested numeric defaults.
- For technical notes, include likely bugs, balancing risks, and edge cases worth guarding in code.

Keep scope tight: everything must fit in one Python file using only the raylib (pyray) library.
Be specific enough that a developer can implement it without asking follow-up questions.
Prefer concrete mechanics, values, and behaviour notes over generic adjectives.
Do not write code.""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    artifacts_on=True,
    artifacts_file_extension=".txt",
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

raylib_developer = Agent(
    agent_name="RaylibDeveloper",
    agent_description="Implements Python raylib games from a Game Design Document",
    system_prompt="""You are an expert Python developer specialising in raylib (pyray) game development.

Given a Game Design Document, write a *complete, runnable* single-file Python game.

Treat the GDD as the implementation spec. Preserve its named mechanics, UI, pacing, and tuning unless a change is required to keep the game playable or technically correct.

Technical requirements:
- Import: `import pyray as rl`  (installed via `pip install raylib`)
- Use rl.Color(r, g, b, a) for all custom colors — never pass raw tuples
- Entry point: if __name__ == "__main__": main()
- Standard raylib loop:
    rl.init_window(width, height, title)
    rl.set_target_fps(60)
    while not rl.window_should_close():
        # update
        rl.begin_drawing()
        rl.clear_background(rl.BLACK)
        # draw
        rl.end_drawing()
    rl.close_window()
- Use only built-in Python + pyray (no pygame, PIL, numpy, etc.)
- Add brief inline comments for each logical section
- Make the game genuinely playable and fun

Output ONLY the Python source code, wrapped in a ```python ... ``` block.""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

code_reviewer = Agent(
    agent_name="CodeReviewer",
    agent_description="Reviews and fixes Python raylib game code for correctness and playability",
    system_prompt="""You are a senior Python developer and game QA engineer.

Given Python raylib (pyray) game code, review and fix it for:
1. Correct pyray API usage — all colors must use rl.Color(r,g,b,a), never raw tuples
2. Complete game loop with proper begin/end drawing calls
3. No missing imports or undefined variables
4. Self-collision check must exclude the tail segment that will vacate this tick (use body[:-1])
5. Logic bugs (off-by-one, division by zero, unchecked list access, etc.)
6. Game feel: controls are responsive, difficulty is fair, win/lose states work

Return the final, corrected, complete Python source code.
Output ONLY the final Python source code, wrapped in a ```python ... ``` block.""",
    model_name=MODEL,
    max_loops=1,
    output_type="final",
    autosave=True,
    artifacts_on=True,
    artifacts_file_extension=".py",
    reasoning_prompt_on=False,
    print_on=False,
    verbose=False,
)

debug_agent = Agent(
    agent_name="DebugAgent",
    agent_description="Fixes Python raylib game code only when static validation reports errors",
    system_prompt="""You are an expert Python debugger specialising in the pyray / raylib library.

You will receive Python game source code together with the output of check_game_code.

Your job:
1. If check_game_code says "No errors found.", return the original code unchanged.
2. If errors are reported, fix the code.
3. You may call check_game_code once on your revised code to verify the fix.
4. Common pyray pitfalls to watch for:
   - Wrong function names: vector2_distance NOT vector_2distance,
     check_collision_circles NOT check_collision_circle, etc.
   - Colors must be rl.Color(r,g,b,a) or named constants like rl.RED — never tuples
   - draw_circle radius must be a float
   - Vector2 fields are .x and .y — not indexable
5. check_game_code does NOT open a window — it uses AST analysis, so it is always safe to call.
6. Output ONLY the final fixed Python source code wrapped in a ```python ... ``` block.
7. Do not include explanations, summaries, or any markdown outside the code block.""",
    model_name=MODEL,
    max_loops=2,
    output_type="final",
    autosave=True,
    tools=[check_game_code],
    reasoning_prompt_on=False,
    tool_call_summary=False,
    show_tool_execution_output=False,
    print_on=False,
    verbose=False,
)

for agent in (
    game_designer,
    raylib_developer,
    code_reviewer,
    debug_agent,
):
    enable_trace_metadata(agent)

# ── AgentRearrange flow ────────────────────────────────────────────────────────

flow = "GameDesigner -> RaylibDeveloper -> CodeReviewer"

gamedev_team = AgentRearrange(
    name="GameDevTeam",
    description="Swarm AI team that designs, codes, and reviews Python raylib games",
    agents=[game_designer, raylib_developer, code_reviewer],
    flow=flow,
    max_loops=1,
    output_type="final",
    verbose=True,
    time_enabled=True,
    message_id_on=True,
)

# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the single-file game swarm."""
    parser = argparse.ArgumentParser(
        description="Generate single-file pyray games with a Swarms team.",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="High-level game request. If omitted, stdin or prompt input is used.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the configured WORKSPACE_DIR before generation.",
    )
    return parser.parse_args()


def resolve_task(args: argparse.Namespace) -> str:
    """Resolve the task from argv, stdin, or interactive input."""
    if isinstance(args.task, str) and args.task.strip():
        return args.task.strip()

    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped

    task = input("\nWhat game do you want to create?\n> ").strip()
    if task:
        return task

    print(f"\n(Using default task: {DEFAULT_TASK})")
    return DEFAULT_TASK


def main() -> None:
    """Run the single-file game generation workflow."""
    args = parse_args()
    if args.clean:
        clean_workspace_dir()

    print("=" * 60)
    print("  Swarms AI GameDev Team — Python Raylib Generator")
    print("  Flow: GameDesigner -> RaylibDeveloper -> CodeReviewer")
    print("  Validation: check_game_code, then DebugAgent only if needed")
    print(f"  Workspace: {os.path.abspath(WORKSPACE_DIR)}")
    if args.clean:
        print("  Clean run: yes")
    print("=" * 60)

    task = resolve_task(args)

    print("\nStarting team...\n")
    result = gamedev_team.run(task)

    gdd = get_final_agent_output(game_designer, task)
    reviewed_output = get_final_agent_output(code_reviewer, str(result))
    reviewed_code = extract_python_code(reviewed_output)

    if not reviewed_code.strip():
        raise RuntimeError("CodeReviewer did not return Python source code.")

    validation_result = check_game_code(reviewed_code)
    final_output = reviewed_output
    final_agent_name = "CodeReviewer"
    final_validation = validation_result

    if validation_result != "No errors found.":
        print("Static validation found issues. Running DebugAgent...\n")
        debug_task = f"""Fix this Python pyray game.

check_game_code output:
{validation_result}

Current code:
```python
{reviewed_code}
```"""
        debug_result = debug_agent.run(debug_task)
        final_output = get_final_agent_output(
            debug_agent, str(debug_result)
        )
        fixed_code = extract_python_code(final_output)
        final_agent_name = "DebugAgent"
        final_validation = check_game_code(fixed_code)
        if final_validation != "No errors found.":
            raise RuntimeError(
                "DebugAgent returned code that still failed static validation:\n"
                + final_validation
            )

    slug = make_game_slug(task)
    game_dir = make_game_dir(slug)
    game_path = save_outputs(final_output, gdd, game_dir)
    trace_path = save_trace(
        build_trace(
            task=task,
            swarm_flow=flow,
            final_agent_name=final_agent_name,
            validation_result=final_validation,
            team_conversation=gamedev_team.conversation,
            agents={
                "GameDesigner": game_designer,
                "RaylibDeveloper": raylib_developer,
                "CodeReviewer": code_reviewer,
                "DebugAgent": debug_agent,
            },
        ),
        game_dir,
    )

    print("\n" + "=" * 60)
    print(f"  Game dir : {game_dir}")
    print(f"  Game file: {game_path}")
    print(f"  GDD file : {os.path.join(game_dir, 'gdd.txt')}")
    print(f"  Trace file: {trace_path}")
    print(f"  Agent states saved under: {os.path.abspath(WORKSPACE_DIR)}/agents/")
    print()
    print("  Install raylib:  .\\venv\\Scripts\\pip install raylib")
    print(f"  Run the game:    .\\venv\\Scripts\\python \"{game_path}\"")
    print("=" * 60)


if __name__ == "__main__":
    main()

