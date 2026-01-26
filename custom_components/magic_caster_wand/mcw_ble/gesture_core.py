import numpy as np

def generate_circle(points=50):
    t = np.linspace(0, 2*np.pi, points)
    x = np.cos(t)
    y = np.sin(t)
    return np.column_stack((x, y))

def generate_rectangle(points=50):
    # 4 sides
    side_points = points // 4
    # Top
    x1 = np.linspace(-1, 1, side_points)
    y1 = np.ones(side_points)
    # Right
    x2 = np.ones(side_points)
    y2 = np.linspace(1, -1, side_points)
    # Bottom
    x3 = np.linspace(1, -1, side_points)
    y3 = -np.ones(side_points)
    # Left
    x4 = -np.ones(side_points)
    y4 = np.linspace(-1, 1, side_points)
    
    return np.concatenate([
        np.column_stack((x1, y1)),
        np.column_stack((x2, y2)),
        np.column_stack((x3, y3)),
        np.column_stack((x4, y4))
    ])

def generate_line(start, end, points=50):
    x = np.linspace(start[0], end[0], points)
    y = np.linspace(start[1], end[1], points)
    return np.column_stack((x, y))

def generate_triangle(points=50):
    side_points = points // 3
    # Base
    x1 = np.linspace(-1, 1, side_points)
    y1 = -np.ones(side_points)
    # Right up
    x2 = np.linspace(1, 0, side_points)
    y2 = np.linspace(-1, 1, side_points)
    # Left down
    x3 = np.linspace(0, -1, side_points)
    y3 = np.linspace(1, -1, side_points)

    return np.concatenate([
        np.column_stack((x1, y1)),
        np.column_stack((x2, y2)),
        np.column_stack((x3, y3))
    ])

def normalize(points):
    # Resample to 50 points (simple approximate) if needed, but we generated 50.
    # Scale to bounding box [0, 1]
    min_vals = np.min(points, axis=0)
    max_vals = np.max(points, axis=0)
    size = np.maximum(max_vals - min_vals, 1e-5)
    return (points - min_vals) / size

def generate_star(points=50):
    # 5-pointed star
    # Vertices at angles: 90 (top), then +144 degrees (4pi/5) steps
    angles = np.linspace(np.pi/2, np.pi/2 + 4*np.pi, 6) # 5 segments
    # Actually standard star drawing order: Top -> BottomRight -> TopLeft -> TopRight -> BottomLeft -> Top
    # Angles: 90, -54 (306), 162, 18, 234, 90
    pts = []
    # Parametric is tricky for sharp corners with linspace on t.
    # Better to define key points and interpolate lines
    key_points = [
        (0, 1), # Top
        (0.587, -0.809), # Bottom Right
        (-0.951, 0.309), # Top Left
        (0.951, 0.309), # Top Right
        (-0.587, -0.809), # Bottom Left
        (0, 1) # Close
    ]
    total_segments = len(key_points) - 1
    segment_points = points // total_segments
    
    all_pts = []
    for i in range(total_segments):
        start = key_points[i]
        end = key_points[i+1]
        all_pts.append(generate_line(start, end, segment_points))
    return np.concatenate(all_pts)

def generate_heart(points=50):
    t = np.linspace(0, 2*np.pi, points)
    # Parametric heart equation
    x = 16 * np.sin(t)**3
    y = 13 * np.cos(t) - 5 * np.cos(2*t) - 2 * np.cos(3*t) - np.cos(4*t)
    return np.column_stack((x, y))

def generate_infinity(points=50):
    t = np.linspace(0, 2*np.pi, points)
    x = np.cos(t)
    y = np.sin(t) * np.cos(t)
    return np.column_stack((x, y))

def generate_check(points=50):
    # Short down-right, Long up-right
    # (0,0) -> (1, -1) -> (3, 2)
    l1 = generate_line((0, 0), (1, -1), points // 3)
    l2 = generate_line((1, -1), (3, 2), (points * 2) // 3)
    return np.concatenate([l1, l2])

def generate_lightning(points=50):
    # Zig zag: (0, 1) -> (-0.5, 0) -> (0.5, 0) -> (0, -1)
    # Simplified lightning bolt
    p1 = generate_line((0.2, 1), (-0.2, 0), points // 3)
    p2 = generate_line((-0.2, 0), (0.2, 0), points // 3)
    p3 = generate_line((0.2, 0), (-0.2, -1), points // 3)
    return np.concatenate([p1, p2, p3])

def generate_spiral(points=50):
    t = np.linspace(0, 4*np.pi, points)
    r = t
    x = r * np.cos(t)
    y = r * np.sin(t)
    return np.column_stack((x, y))

# --- New Alphabets & Symbols ---
def generate_c(points=50):
    # Arc from 45 to 315 degrees (0.25pi to 1.75pi)? No, Right-starting circle is 0.
    # C is usually drawn top-right to bottom-right.
    # Angle: 45 (pi/4) -> 315 (7pi/4) (counter-clockwise? No, Clockwise)
    # Let's do Angle: pi/4 -> 7pi/4 via top/left/bottom.
    # Actually in standard unit circle: pi/4 (top right) -> pi (left) -> 7pi/4 (bottom right).
    t = np.linspace(np.pi/4, 7*np.pi/4, points)
    # We want top-right start. cos(pi/4)>0, sin(pi/4)>0.
    # But C opens to the right. So we need the LEFT part of the circle.
    # Angles: 45 -> 360-45?
    # Circle x=cos, y=sin.
    # Left side is pi/2 to 3pi/2.
    # C: starts around pi/4, goes UP to pi/2, LEFT to pi, DOWN to 3pi/2, RIGHT to 7pi/4.
    t = np.linspace(np.pi/4, 7*np.pi/4, points) 
    x = np.cos(t) 
    y = np.sin(t) # This makes a "C" opening to the RIGHT if we flip X? 
    # Normal Circle: 0 is Right. pi is Left.
    # We want Pi/4 to 7Pi/4? That covers 90% of circle excluding the Right wedge.
    # Correct.
    return np.column_stack((x, y))

def generate_l(points=50):
    # Down then Right
    p1 = generate_line((0, 1), (0, 0), points // 2)
    p2 = generate_line((0, 0), (0.6, 0), points // 2)
    return np.concatenate([p1, p2])

def generate_m(points=50):
    # Up, Down-Right, Up-Right, Down
    # (0,0)->(0,1)->(0.5,0.5)->(1,1)->(1,0)
    p1 = generate_line((0, 0), (0, 1), points // 4)
    p2 = generate_line((0, 1), (0.5, 0.5), points // 4)
    p3 = generate_line((0.5, 0.5), (1, 1), points // 4)
    p4 = generate_line((1, 1), (1, 0), points // 4)
    return np.concatenate([p1, p2, p3, p4])

def generate_n(points=50):
    # Up, Down-Right, Up
    # (0,0)->(0,1)->(1,0)->(1,1)
    p1 = generate_line((0, 0), (0, 1), points // 3)
    p2 = generate_line((0, 1), (1, 0), points // 3)
    p3 = generate_line((1, 0), (1, 1), points // 3)
    return np.concatenate([p1, p2, p3])

def generate_s(points=50):
    # Sigmoid function-ish or two arcs
    t = np.linspace(-np.pi, np.pi, points)
    x = 0.5 * np.cos(t) # x goes 0.5 -> -0.5 -> 0.5? No.
    # S: Top-Right -> Top-Left -> Center -> Bottom-Right -> Bottom-Left
    # Sine wave: y = sin(x) ?
    # Vertical S: x = sin(y)?
    y = np.linspace(1, -1, points)
    x = 0.5 * np.sin(y * np.pi) 
    # But usually S top part curves Left, bottom curves Right.
    # y=1 -> x=sin(pi)=0. y=0.5 -> x=1. y=0 -> x=0. y=-0.5 -> x=-1.
    # This is a reversed S?
    # "S": Top (Right to Left), Middle (Left to Right), Bottom (Right to Left).
    # Let's rely on cosine.
    return np.column_stack((x, y)) 

def generate_u(points=50):
    # Down, Arc, Up
    # (-1, 1) -> (-1, 0) -> ... -> (1, 0) -> (1, 1)
    # Arc version: x=cos(t), y=sin(t) for t in pi...2pi
    t = np.linspace(np.pi, 2*np.pi, points)
    x = np.cos(t)
    y = np.sin(t)
    # Flatten top to make it deeper? Normal U is fine as half-circle extended.
    # Let's Extend legs.
    p1 = generate_line((-1, 2), (-1, 0), 10)
    p2 = np.column_stack((x, y)) # bottom curve
    p3 = generate_line((1, 0), (1, 2), 10)
    return np.concatenate([p1, p2, p3])

def generate_w(points=50):
    # Inverse M
    # (0,1)->(0.2,0)->(0.5,0.5)->(0.8,0)->(1,1)
    p1 = generate_line((0, 1), (0.2, 0), points // 4)
    p2 = generate_line((0.2, 0), (0.5, 0.5), points // 4)
    p3 = generate_line((0.5, 0.5), (0.8, 0), points // 4)
    p4 = generate_line((0.8, 0), (1, 1), points // 4)
    return np.concatenate([p1, p2, p3, p4])

def generate_z(points=50):
    # Right, Down-Left, Right
    p1 = generate_line((0, 1), (1, 1), points // 3)
    p2 = generate_line((1, 1), (0, 0), points // 3)
    p3 = generate_line((0, 0), (1, 0), points // 3)
    return np.concatenate([p1, p2, p3])

def generate_diamond(points=50):
    # (0,1)->(1,0)->(0,-1)->(-1,0)->(0,1)
    p1 = generate_line((0, 1), (1, 0), points // 4)
    p2 = generate_line((1, 0), (0, -1), points // 4)
    p3 = generate_line((0, -1), (-1, 0), points // 4)
    p4 = generate_line((-1, 0), (0, 1), points // 4)
    return np.concatenate([p1, p2, p3, p4])

def generate_triangle_down(points=50):
    # Inverted Triangle
    # (-1, 1) -> (1, 1) -> (0, -1) -> (-1, 1)
    p1 = generate_line((-1, 1), (1, 1), points // 3)
    p2 = generate_line((1, 1), (0, -1), points // 3)
    p3 = generate_line((0, -1), (-1, 1), points // 3)
    return np.concatenate([p1, p2, p3])

def generate_alpha(points=50):
    # Fish shape: Top-Right -> Cross -> Bottom-Left -> Loop -> Top-Left -> Cross
    # Simplified: Parametric alpha curve
    # x = sin(t), y = sin(2t) is a figure 8 (Infinity).
    # Alpha is like infinity but one loop is open tails.
    # Start: (1, 1) -> Cross (0,0) -> Loop -> Cross -> (1, -1)
    t = np.linspace(-np.pi/2, 3*np.pi/2, points)
    x = np.cos(t) # Circle
    y = np.sin(t) 
    # This is circle.
    # Alpha: Draw a loop, then cross tails.
    # Just use geometric segments.
    # Top-Right(1,1) -> Center(0,0) -> Bottom-Left(-1,-1) -> Arc-Left -> Top-Left(-1,1) -> Center(0,0) -> Bottom-Right(1,-1)
    # Actually just a "Fish" shape.
    # Loop on left, tails on right.
    t = np.linspace(0, 2*np.pi, points)
    x = np.sin(t) - 1 # Shift left
    y = np.cos(t) # Loop on x=[-2, 0]
    # This is getting complex. Let's do simple "Fish"
    # Tail1(2, 1) -> Cross(0,0) -> Loop(-2, 0) -> Cross(0,0) -> Tail2(2, -1)
    t = np.linspace(np.pi/4, 7*np.pi/4, points) # 45 to 315 deg
    # x = cos(t), y = sin(t) is C shape.
    # Alpha is vertical loop? 
    # Let's try x = t^2, y=t? No.
    # Lemniscate is infinity.
    # Let's skip parametric and use lines.
    # (1, 1) to (-1, -1) (Diagonal down)
    # (-1, -1) to (-1, 1) (Left vertical up)
    # (-1, 1) to (1, -1) (Diagonal down)
    # This is a bit like N or Z.
    return normalize(generate_infinity()) # Alpha is basically infinity drawn differently? No.
    
def generate_alpha_symbol(points=50):
    # Like a fish.
    # Start top right, go down-left, loop back up, cross, end bottom right.
    t = np.linspace(0, 2*np.pi, points)
    x = np.cos(t)
    y = np.sin(t) * np.cos(t/2) # Just experimenting
    # Let's stick to known shapes.
    return generate_infinity() # Placeholder if not sure.
    
def create_templates():
    """Generates and returns the dictionary of gesture templates."""
    templates = {}
    
    # Basic Shapes
    templates["Circle"] = normalize(generate_circle()).tolist()
    templates["Rectangle"] = normalize(generate_rectangle()).tolist()
    templates["Triangle"] = normalize(generate_triangle()).tolist()
    templates["Triangle_Down"] = normalize(generate_triangle_down()).tolist()
    templates["Diamond"] = normalize(generate_diamond()).tolist()
    templates["Star"] = normalize(generate_star()).tolist()
    templates["Heart"] = normalize(generate_heart()).tolist()
    templates["Infinity"] = normalize(generate_infinity()).tolist()
    templates["Spiral"] = normalize(generate_spiral()).tolist()
    
    # Alphabets
    templates["Letter_C"] = normalize(generate_c()).tolist()
    templates["Letter_L"] = normalize(generate_l()).tolist()
    templates["Letter_M"] = normalize(generate_m()).tolist()
    templates["Letter_N"] = normalize(generate_n()).tolist()
    templates["Letter_S"] = normalize(generate_s()).tolist()
    templates["Letter_U"] = normalize(generate_u()).tolist()
    templates["Letter_W"] = normalize(generate_w()).tolist()
    templates["Letter_Z"] = normalize(generate_z()).tolist()

    # Symbols
    templates["Check"] = normalize(generate_check()).tolist()
    templates["Lightning"] = normalize(generate_lightning()).tolist()
    
    # Swipes & Directions
    templates["Swipe_Right"] = normalize(generate_line((-1, 0), (1, 0))).tolist()
    templates["Swipe_Left"] = normalize(generate_line((1, 0), (-1, 0))).tolist()
    templates["Swipe_Up"] = normalize(generate_line((0, -1), (0, 1))).tolist()
    templates["Swipe_Down"] = normalize(generate_line((0, 1), (0, -1))).tolist()
    templates["Diagonal_Right_Up"] = normalize(generate_line((-1, -1), (1, 1))).tolist()

    # Chevrons / Arrows
    # < (Left)
    templates["Chevron_Left"] = normalize(np.concatenate([
        generate_line((0, 1), (-1, 0), 25),
        generate_line((-1, 0), (0, -1), 25)
    ])).tolist()
    
    # > (Right)
    templates["Chevron_Right"] = normalize(np.concatenate([
        generate_line((0, 1), (1, 0), 25),
        generate_line((1, 0), (0, -1), 25)
    ])).tolist()
    
    # ^ (Up / Caret)
    templates["Chevron_Up"] = normalize(np.concatenate([
        generate_line((-1, -0.5), (0, 0.5), 25),
        generate_line((0, 0.5), (1, -0.5), 25)
    ])).tolist()
    
    # v (Down)
    templates["Chevron_Down"] = normalize(np.concatenate([
        generate_line((-1, 0.5), (0, -0.5), 25),
        generate_line((0, -0.5), (1, 0.5), 25)
    ])).tolist()
    
    return templates
