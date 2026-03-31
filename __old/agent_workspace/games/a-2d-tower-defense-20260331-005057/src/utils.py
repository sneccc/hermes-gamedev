import pyray as rl
import math
import random

def get_distance(v1, v2):
    return math.sqrt((v1.x - v2.x)**2 + (v1.y - v2.y)**2)

def lerp_vec2(v1, v2, t):
    return rl.Vector2(v1.x + (v2.x - v1.x) * t, v1.y + (v2.y - v1.y) * t)

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, pos, color, count=10):
        for _ in range(count):
            self.particles.append({
                "pos": rl.Vector2(pos.x, pos.y),
                "vel": rl.Vector2(random.uniform(-2, 2), random.uniform(-2, 2)),
                "life": 1.0,
                "color": color
            })

    def update(self, dt):
        for p in self.particles[:]:
            p["pos"].x += p["vel"].x * 60 * dt
            p["pos"].y += p["vel"].y * 60 * dt
            p["life"] -= dt * 2
            if p["life"] <= 0:
                self.particles.remove(p)

    def draw(self):
        for p in self.particles:
            alpha = int(p["life"] * 255)
            c = rl.Color(p["color"].r, p["color"].g, p["color"].b, alpha)
            rl.draw_circle_v(p["pos"], 2, c)
