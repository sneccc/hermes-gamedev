import math
import pyray as rl

def normalize_vector3(v):
    return rl.vector3_normalize(v)

def cross_product(v1, v2):
    return rl.vector3_cross_product(v1, v2)

def quaternion_from_axis_angle(axis, angle):
    return rl.quaternion_from_axis_angle(axis, angle)

def quaternion_multiply(q1, q2):
    return rl.quaternion_multiply(q1, q2)

def vector3_rotate_by_quaternion(v, q):
    return rl.vector3_rotate_by_quaternion(v, q)
