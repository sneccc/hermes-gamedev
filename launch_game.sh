#!/usr/bin/env bash
# launch_game.sh — Start the overstory coordinator to build a raylib game
# Usage: ./launch_game.sh "A top-down arena shooter with WASD, mouse aim, waves"
#
# This opens an interactive tmux session where the coordinator:
#   1. Creates task issues for the game
#   2. Dispatches a scout to design the GDD
#   3. Dispatches builders oimplementing each module
#   4. Dispatches a reviewer to validate the pyray API
#   5. Merges everything and reports completion

set -euo pipefail
cd "$(dirname "$0")"

GAME_DESC="${1:?Usage: $0 \"<game description>\"}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
SLUG=$(echo "$GAME_DESC" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]//g' | awk '{for(i=1;i<=4&&i<=NF;i++) printf "%s-",$i; print ""}' | sed 's/-$//')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Overstory Raylib Game Generator"
echo "  Game: $GAME_DESC"
echo "  Slug: $SLUG-$TIMESTAMP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create the game skeleton
GAME_DIR="games/${SLUG}-${TIMESTAMP}"
mkdir -p "$GAME_DIR"/{src,data,docs}
cat > "$GAME_DIR/manifest.json" <<EOF
{
  "name": "$SLUG",
  "description": "$GAME_DESC",
  "created": "$(date -Iseconds)",
  "status": "in-progress",
  "files": []
}
EOF

git add "$GAME_DIR"
git commit -m "scaffold: $SLUG game directory"

echo ""
echo "Starting coordinator... (attach to tmux with: ov dashboard)"
echo ""

# Start the coordinator with the game objective
ov coordinator start --attach <<EOF
Build a complete Python raylib game: $GAME_DESC

Target directory: $GAME_DIR/
Follow the project structure in CLAUDE.md.

Decompose into:
1. Scout: Research and write a detailed GDD to $GAME_DIR/docs/gdd.md
2. Builder (constants): Create $GAME_DIR/src/constants.py with all tuning values
3. Builder (entities): Create $GAME_DIR/src/entities.py with game objects
4. Builder (systems): Create $GAME_DIR/src/systems.py with game logic
5. Builder (ui): Create $GAME_DIR/src/ui.py with HUD and menus
6. Builder (main): Create $GAME_DIR/src/main.py tying everything together
7. Reviewer: Validate all pyray API calls and cross-file imports

Quality gates: python3 -m py_compile on every .py file, pyray API validation.
EOF
