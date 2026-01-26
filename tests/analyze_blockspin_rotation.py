"""Analyze BlockSpin rotation matrices to determine correct UV mapping.

This script simulates the rotation matrices used in the BlockSpin shader
to determine what UV transformation is needed for each direction.
"""
import numpy as np
import math

def rotation_matrix_y(angle):
    """Y-axis rotation matrix (horizontal spin)."""
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([
        [c,  0, s],
        [0,  1, 0],
        [-s, 0, c]
    ])

def rotation_matrix_x(angle):
    """X-axis rotation matrix (vertical spin)."""
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([
        [1, 0,  0],
        [0, c, -s],
        [0, s,  c]
    ])

def rotation_matrix_diagonal(angle):
    """Diagonal rotation matrix (combined X+Y)."""
    rot_y = rotation_matrix_y(angle)
    rot_x = rotation_matrix_x(angle)
    return rot_y @ rot_x

def analyze_back_face_orientation(rot_matrix, direction_name):
    """Analyze how the back face normal is oriented after rotation."""
    # Back face normal points in -Z direction initially
    back_normal = np.array([0, 0, -1])
    
    # After 180° rotation
    rotated_normal = rot_matrix @ back_normal
    
    print(f"\n{direction_name}:")
    print(f"  Initial back normal: {back_normal}")
    print(f"  After 180° rotation: {rotated_normal}")
    
    # Analyze what this means for UV
    # If the normal flips in X, we need to flip U
    # If the normal flips in Y, we need to flip V
    
    # The back face at angle=0 has normal pointing -Z
    # At angle=π, it should point +Z (facing camera)
    # But the rotation also affects the texture orientation
    
    # Check corner points to understand UV transformation
    # Bottom-left corner of back face: (-1, -1, -depth)
    # After rotation, where does it end up?
    corner_bl = np.array([-1, -1, 0])
    corner_br = np.array([1, -1, 0])
    corner_tl = np.array([-1, 1, 0])
    corner_tr = np.array([1, 1, 0])
    
    rotated_bl = rot_matrix @ corner_bl
    rotated_br = rot_matrix @ corner_br
    rotated_tl = rot_matrix @ corner_tl
    rotated_tr = rot_matrix @ corner_tr
    
    print(f"  Corner transformations (back face):")
    print(f"    BL (-1,-1) -> ({rotated_bl[0]:.2f}, {rotated_bl[1]:.2f})")
    print(f"    BR ( 1,-1) -> ({rotated_br[0]:.2f}, {rotated_br[1]:.2f})")
    print(f"    TL (-1, 1) -> ({rotated_tl[0]:.2f}, {rotated_tl[1]:.2f})")
    print(f"    TR ( 1, 1) -> ({rotated_tr[0]:.2f}, {rotated_tr[1]:.2f})")
    
    # Determine UV transformation needed
    # If BL ends up at BR position, we need to flip U
    # If BL ends up at TL position, we need to flip V
    
    uv_transform = []
    if abs(rotated_bl[0] - 1) < 0.1:  # BL moved to right
        uv_transform.append("FLIP U (1.0 - u)")
    if abs(rotated_bl[1] - 1) < 0.1:  # BL moved to top
        uv_transform.append("FLIP V (1.0 - v)")
    
    if uv_transform:
        print(f"  UV Transform needed: {', '.join(uv_transform)}")
    else:
        print(f"  UV Transform needed: NONE (use raw UVs)")
    
    return uv_transform

print("=== BlockSpin Rotation Analysis ===")
print("Analyzing 180° rotations for each direction")

# LEFT: Y-axis, positive angle
print("\n" + "="*50)
rot_y_pos = rotation_matrix_y(math.pi)
analyze_back_face_orientation(rot_y_pos, "LEFT (Y-axis, +π)")

# RIGHT: Y-axis, negative angle
print("\n" + "="*50)
rot_y_neg = rotation_matrix_y(-math.pi)
analyze_back_face_orientation(rot_y_neg, "RIGHT (Y-axis, -π)")

# UP: X-axis, positive angle
print("\n" + "="*50)
rot_x_pos = rotation_matrix_x(math.pi)
analyze_back_face_orientation(rot_x_pos, "UP (X-axis, +π)")

# DOWN: X-axis, negative angle
print("\n" + "="*50)
rot_x_neg = rotation_matrix_x(-math.pi)
analyze_back_face_orientation(rot_x_neg, "DOWN (X-axis, -π)")

# DIAG_TL_BR: Diagonal, positive angle
print("\n" + "="*50)
rot_diag_pos = rotation_matrix_diagonal(math.pi)
analyze_back_face_orientation(rot_diag_pos, "DIAG_TL_BR (Diagonal, +π)")

# DIAG_TR_BL: Diagonal, negative angle
print("\n" + "="*50)
rot_diag_neg = rotation_matrix_diagonal(-math.pi)
analyze_back_face_orientation(rot_diag_neg, "DIAG_TR_BL (Diagonal, -π)")

print("\n" + "="*50)
print("\nSUMMARY:")
print("Based on the corner transformations, the correct UV mapping is:")
print("  LEFT:        FLIP U")
print("  RIGHT:       FLIP U")
print("  UP:          FLIP V")
print("  DOWN:        FLIP V")
print("  DIAG_TL_BR:  FLIP U and V")
print("  DIAG_TR_BL:  FLIP U and V")
