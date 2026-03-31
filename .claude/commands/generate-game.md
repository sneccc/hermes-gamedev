Generate a new Python raylib game from the user's idea.

## Steps

1. Read SPEC.md and CLAUDE.md for project conventions
2. Create the game directory skeleton under `games/<slug>-<timestamp>/`
3. Create the `manifest.json` with game metadata
4. Start the overstory coordinator to dispatch the agent swarm:
   - Scout: Research and expand the idea into a detailed GDD
   - Builders: Implement each module (constants, entities, systems, ui, utils, main)
   - Reviewer: Validate pyray API calls and cross-file imports
5. All agents follow the raylib conventions in CLAUDE.md
6. Quality gates must pass before any module is considered done

## Game Idea

$ARGUMENTS
