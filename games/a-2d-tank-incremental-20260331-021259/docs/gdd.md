# Tank Tycoon: Iron Idle - Game Design Document

## 1. Overview
**Tank Tycoon: Iron Idle** is a 2D incremental game where the player controls a tank that automatically defends against waves of incoming geometric targets. The goal is to accumulate "Scrap" to upgrade the tank's capabilities and reach higher waves.

## 2. Core Loop
1. **Combat**: Tank automatically targets and shoots at the nearest target.
2. **Collection**: Destroyed targets drop Scrap (or Scrap is awarded directly).
3. **Upgrade**: Spend Scrap in the shop to increase Fire Rate, Damage, and other stats.
4. **Progression**: Waves get progressively harder with more and tougher targets.

## 3. Gameplay Mechanics

### 3.1 The Tank
- Fixed in the center of the screen (or bottom).
- Rotates to track the closest enemy.
- Fires projectiles automatically.

### 3.2 Enemies (Targets)
- Simple geometric shapes (Squares, Triangles, Hexagons).
- Move from edges towards the center.
- Different colors represent different health/scrap values.

### 3.3 Upgrades
- **Fire Rate**: Decreases time between shots.
- **Attack Damage**: Increases damage per projectile.
- **Bullet Speed**: Increases projectile velocity.
- **Multi-Shot**: Adds additional barrels/projectiles.
- **Critical Chance**: Chance to deal double damage.
- **Scrap Multiplier**: Increases scrap earned per kill.

## 4. Visual Style
- **Minimalist Geometric Art**: All entities are basic shapes.
- **Color Palette**: Dark background (Black/Dark Grey) with vibrant neon colors for the tank and enemies.
- **Feedback**: Simple particle explosions when targets are destroyed.

## 5. UI Elements
- **Top Bar**: Current Scrap count, Wave number.
- **Side/Bottom Menu**: Upgrade shop with buttons showing cost and current level.
- **Game Area**: The central combat zone.

## 6. Technical Constraints (Raylib)
- Resolution: 1024x768.
- Target FPS: 60.
- Module-based structure (`entities.py`, `systems.py`, etc.).
