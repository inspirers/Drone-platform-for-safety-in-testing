import numpy as np 
from scipy.spatial import ConvexHull
from CoordinateHandler import Coordinate

coordslist = {
    "point_1": Coordinate(37.7749, -122.4194, 15.2),
    "point_2": Coordinate(40.7128, -74.0060, 10.5),
    "point_3": Coordinate(34.0522, -118.2437, 305.4),
    "point_4": Coordinate(51.5074, -0.1278, 25.0),
    "point_5": Coordinate(48.8566, 2.3522, 35.8),
    "point_6": Coordinate(-33.8688, 151.2093, 58.6),
    "point_7": Coordinate(35.6895, 139.6917, 40.3),
    "point_8": Coordinate(-22.9068, -43.1729, 5.7),
    "point_9": Coordinate(55.7558, 37.6173, 144.9),
    "point_10": Coordinate(19.4326, -99.1332, 2240.1),
}

coords = np.array([[item.lat, item.lng] for item in coordslist.values()])

# ----

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

# Compute the minimum area rectangle
rect = min_area_rectangle_of_points(coords)

# Extract rectangle properties
axis = np.array(rect.axis)
center = np.array(rect.center)
extent = np.array(rect.extent)

# Adjust overlap parameter O, where O=0 means no overlap, and O=1 means full overlap
O = 0.2  # Change this to test different overlaps

# Determine the longer side and shorter side of the rectangle
longer_extent = max(extent)
shorter_extent = min(extent)

# Compute the square size based on the longer extent to ensure full coverage
square_size = longer_extent

# Compute the overlap and offset for the two squares
overlap = O * longer_extent
split_offset = (1 - O) * longer_extent
split_axis = axis[0] if extent[0] > extent[1] else axis[1]

# Calculate the centers of the two squares
square1_center = center - split_offset / 2 * split_axis
square2_center = center + split_offset / 2 * split_axis

# Return square centers as tuples
square1_center_tuple = tuple(square1_center)
square2_center_tuple = tuple(square2_center)

print("Square 1 Center:", square1_center_tuple)
print("Square 2 Center:", square2_center_tuple)

