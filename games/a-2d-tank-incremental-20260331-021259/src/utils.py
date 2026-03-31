import math
import pyray as rl


def vector2_distance(v1, v2):
    return math.hypot(v1.x - v2.x, v1.y - v2.y)


def vector2_normalize(v):
    length = math.hypot(v.x, v.y)
    if length == 0:
        return rl.Vector2(0, 0)
    return rl.Vector2(v.x / length, v.y / length)


def vector2_add(v1, v2):
    return rl.Vector2(v1.x + v2.x, v1.y + v2.y)


def vector2_sub(v1, v2):
    return rl.Vector2(v1.x - v2.x, v1.y - v2.y)


def vector2_scale(v, scalar):
    return rl.Vector2(v.x * scalar, v.y * scalar)


def angle_between_vectors(origin, target):
    """Returns angle in radians between origin and target vector"""
    return math.atan2(target.y - origin.y, target.x - origin.x)


def check_circle_collision(pos1, r1, pos2, r2):
    return vector2_distance(pos1, pos2) <= (r1 + r2)
