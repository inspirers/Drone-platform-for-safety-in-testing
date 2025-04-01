import numpy as np
from scipy.spatial import ConvexHull
import matplotlib.pyplot as plt

class Rectangle:
    def __init__(self):
        self.center = np.array([0.0, 0.0])
        self.axis = [np.array([0.0, 0.0]), np.array([0.0, 0.0])]
        self.extent = [0.0, 0.0]
        self.area = float('inf')

def normalize(v):
    return v / np.linalg.norm(v)

def perp(v):
    return np.array([-v[1], v[0]])

def dot(v1, v2):
    return np.dot(v1, v2)

def min_area_rectangle_of_hull(polygon):
    min_rect = Rectangle()
    n = len(polygon)
    
    for i0 in range(n):
        i1 = (i0 + 1) % n
        origin = polygon[i0]
        U0 = polygon[i1] - origin
        U0 = normalize(U0)
        U1 = perp(U0)
        
        min0, max0 = 0, 0
        max1 = 0  # min1 is guaranteed to be 0
        
        for j in range(n):
            D = polygon[j] - origin
            dot0 = dot(U0, D)
            min0 = min(min0, dot0)
            max0 = max(max0, dot0)
            
            dot1 = dot(U1, D)
            max1 = max(max1, dot1)
        
        area = (max0 - min0) * max1
        
        if area < min_rect.area:
            min_rect.center = origin + ((min0 + max0) / 2) * U0 + (max1 / 2) * U1
            min_rect.axis[0] = U0
            min_rect.axis[1] = U1
            min_rect.extent[0] = (max0 - min0) / 2
            min_rect.extent[1] = max1 / 2
            min_rect.area = area
    
    return min_rect

def compute_convex_hull(points):
    hull = ConvexHull(points)
    return [points[i] for i in hull.vertices]

def min_area_rectangle_of_points(points):
    polygon = compute_convex_hull(points)
    return min_area_rectangle_of_hull(polygon)

# Sample points
coords = np.array([
    [-10.0, 15.5],
    [5.2, -10.3],
    [-15.3, 8.4],
    [12.0, -4.7],
    [-8.1, 13.3],
    [16.5, -19.0],
    [-2.4, 2.2],
    [10.8, -11.5],
    [-5.0, 19.9],
    [20.0, 5.0],
    [-12.3, -6.6],
    [0.0, 14.2],
    [-17.4, 9.5],
    [4.6, -18.1],
    [-20.0, -2.0],
    [15.0, 0.0],
    [-9.9, 17.8],
    [18.5, -14.3],
    [-6.4, 3.3],
    [11.1, -7.2]
])

# Compute the minimum area rectangle
rect = min_area_rectangle_of_points(coords)
print(rect.area)

# Extract rectangle properties
axis = np.array(rect.axis)
center = np.array(rect.center)
extent = np.array(rect.extent)

# Compute the four corners of the rectangle
corners = np.array([
    center + extent[0] * axis[0] + extent[1] * axis[1],
    center + extent[0] * axis[0] - extent[1] * axis[1],
    center - extent[0] * axis[0] - extent[1] * axis[1],
    center - extent[0] * axis[0] + extent[1] * axis[1],
    center + extent[0] * axis[0] + extent[1] * axis[1]  # Close the rectangle
])

# Plot everything
plt.figure()
plt.scatter(coords[:, 0], coords[:, 1], label="Input Points", color="blue")
plt.scatter(center[0], center[1], label="Center", color="red")
plt.plot(corners[:, 0], corners[:, 1], label="Min Area Rectangle", color="green")
plt.show()