# Neon Bastion

- Genre: Tower Defense
- Profile: prototype
- Entrypoint: src/main.py
- Resolution: 1280x720
- Summary: A minimalist 2D tower defense where players defend a central core against geometric waves using modular turrets and energy management.

## Design Pillars
- Geometric Clarity: Use simple shapes and colors to communicate threat and power.
- Resource Tension: Balance spending on new towers versus upgrading existing ones.
- Pathing Predictability: Enemies follow a fixed path to allow for strategic placement.

## Player Fantasy
A tactical commander managing a high-tech energy grid to repel an endless digital swarm.

## Target Session
10-15 minutes per run, escalating in intensity until the core is breached.

## Core Loop
Kill enemies to gain Credits -> Spend Credits to place or upgrade Towers -> Defend Core from increasing waves -> Manage Energy limits.

## Moment To Moment
The player watches a wave of red triangles enter the path. They click a 'Pulse' tower slot to build a fast-firing turret. As enemies die, yellow 'Credit' particles fly to the HUD. The player notices a heavy blue square approaching and quickly upgrades a 'Beam' tower to increase its armor penetration before it reaches the core.

## Controls
- Mouse Left Click: Select build slot / Purchase tower / Upgrade tower
- Mouse Right Click: Cancel selection / Sell tower
- Space: Start next wave / Toggle 2x Speed
- Escape: Pause menu

## Player Kit
- Movement: Static camera, cursor-based interaction with a 2D grid.
- Offense: Automated towers with varying fire rates, ranges, and damage types.
- Defense: The Core (Health: 100). If it reaches 0, game over.
- Resources:
  - Credits: Gained per kill, used for building/upgrading.
  - Energy: Global cap on total active towers.

## Game Objects
-
  - Name: Core
  - Role: Defense Target
  - Behaviour: Static at path end. Pulses when hit. Triggers Game Over at 0 HP.
  - Interactions: Collides with enemies to take damage.
  - Tuning: Health: 100, Pulse Radius: 40px
-
  - Name: Swarmer
  - Role: Basic Enemy
  - Behaviour: Fast, low health, follows path strictly.
  - Spawn Rules: High frequency in early waves.
  - Tuning: HP: 10, Speed: 150px/s, Value: 5
-
  - Name: Tank
  - Role: Heavy Enemy
  - Behaviour: Slow, high health, large size.
  - Spawn Rules: Introduced at wave 5.
  - Tuning: HP: 100, Speed: 60px/s, Value: 25
-
  - Name: Pulse Tower
  - Role: Standard Turret
  - Behaviour: Fires circular projectiles at nearest target.
  - Interactions: Upgradable range and fire rate.
  - Tuning: Cost: 50, Range: 150, Damage: 5, Cooldown: 0.5s
-
  - Name: Beam Tower
  - Role: Sniper Turret
  - Behaviour: Fires a continuous line at the furthest enemy in range.
  - Interactions: High damage, slow tick rate.
  - Tuning: Cost: 150, Range: 300, Damage: 20, Cooldown: 1.5s

## Systems
- Pathfinding: Pre-defined waypoint list. Enemies interpolate between points linearly.
- Combat: Towers scan for targets in range using distance checks. Projectiles are simple circles with velocity.
- Spawning: Wave-based system. Each wave has a 'budget' that it spends on enemy types.
- Economy: Kill-based rewards. Costs scale by 1.5x per upgrade level.
- Feedback: Screen shake on core damage. Particle bursts on enemy death. Color flash on tower fire.

## Progression
- Wave Structure: Wave N = Wave N-1 * 1.2 budget. Every 5 waves introduces a new enemy variant.
- Escalation: Speed of enemies increases by 5% every 3 waves.
- Rewards: Bonus credits for finishing a wave quickly.

## Difficulty Curve
- Early: Waves 1-5: Teaching placement. Low enemy density.
- Mid: Waves 6-15: Introducing mixed groups (Swarmer + Tank). Requires tower variety.
- Late: Waves 16+: High speed, high health swarms. Requires optimized upgrade paths.

## UI And HUD
- Hud: Top bar: Credits, Health, Wave Number. Bottom bar: Tower selection buttons.
- Overlays: Tower range circles visible on hover. Upgrade/Sell menu appears on click.
- State: Main Menu -> Game Loop -> Game Over (with final wave count).

## Visual Style
- Background: Dark grey grid (32x32px cells).
- Path: Slightly lighter grey path with neon blue borders.
- Entities: Enemies are Red/Orange shapes. Towers are Cyan/Green shapes. Projectiles are White/Yellow.

## Technical Notes
- Collision: Use simple circle-circle or circle-point distance checks for performance.
- Modular Design: Towers should inherit from a base class. Enemies should use a state machine for pathing.
- Performance: Pool projectiles and particles to avoid GC spikes during heavy waves.

## Edge Cases
- Path Blocking: The system uses fixed slots next to the path, so players cannot block the path entirely.
- Simultaneous Death: If an enemy reaches the core and dies at the same frame, core damage takes priority.
- Resolution Scaling: Fixed 720p logic with letterboxing if window is resized.

## Win And Lose
- Win Condition: Survival (Endless mode, high score based on waves).
- Lose Condition: Core health reaches 0.

## Tuning Values
- Initial Credits: 200
- Core Max Health: 100
- Base Spawn Interval: 1.0
- Min Spawn Interval: 0.2
- Sell Refund Rate: 0.7

## Content Beats
- Wave 1: 10 Swarmers, slow pace.
- Wave 5: First Tank appears.
- Wave 10: Fast Swarmer rush.
- Wave 20: The 'Wall' - multiple Tanks with Swarmer support.

## Planned Source Files
-
  - Path: src/main.py
  - Purpose: Entry point: Initializes pyray, manages the high-level state machine (Menu, Play, GameOver).
-
  - Path: src/engine.py
  - Purpose: Core game loop: Handles updates, drawing, and system orchestration (Spawning, Combat).
-
  - Path: src/entities.py
  - Purpose: Class definitions for Core, Enemy, Tower, and Projectile.
-
  - Path: src/ui.py
  - Purpose: UI rendering logic, button handling, and HUD layout.
-
  - Path: src/utils.py
  - Purpose: Math helpers, path interpolation, and particle system.
-
  - Path: src/constants.py
  - Purpose: Global constants, color definitions, and config loader.

## Planned Data Files
-
  - Path: data/config.json
  - Purpose: Balance settings and wave definitions.
  - Keys:
    - tower_stats
    - enemy_stats
    - wave_data
    - colors
