import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
from random import randint, choice

class Coordinate:
    def __init__(self, lat, lng, alt=0):
        self.lat = lat
        self.lng = lng
        self.alt = alt

def calculate_Height(area):
    return np.sqrt(area) * 10  # Example scaling function

def getDronesLoc(coordslist, droneOrigin, n_drones=2, overlap=1):
    coords = []
    for coordList in coordslist.values():
        for coord in coordList:
            x = coord.lng
            y = coord.lat
            coords.append([x, y])
    
    coords = np.array(coords)

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
            U0 = normalize(polygon[i1] - origin)
            U1 = perp(U0)
            
            min0, max0 = 0, 0
            max1 = 0  
            
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

    rect = min_area_rectangle_of_hull(compute_convex_hull(coords))
    axis = np.array(rect.axis)
    center = np.array(rect.center)
    extent = np.array(rect.extent)
    
    # Calculate the longer extent
    longer_extent = max(extent)
    # Calculate the square size needed to cover the rectangle (taking overlap into account)
    square_size = (longer_extent * 2) / np.sqrt(n_drones)  # Increase square size to cover the area

    # Adjust the offset to match the increased square size
    split_axis = axis[0] if extent[0] > extent[1] else axis[1]
    split_offset = square_size * (1 - overlap)
    
    drone_centers = [center + (i - (n_drones - 1) / 2) * split_offset * split_axis for i in range(n_drones)]
    
    flyTo_coords = []
    for drone_center in drone_centers:
        drone_loc_x = drone_center[0]
        drone_loc_y = drone_center[1]
        
        delta_lat = drone_loc_x / 6371000 * (180 / np.pi)
        delta_long = (drone_loc_y / (6371000 * np.cos(droneOrigin.lat * np.pi / 180))) * (180 / np.pi)
        
        lat = droneOrigin.lat + delta_lat
        long = droneOrigin.lng + delta_long
        
        flyTo_coords.append(Coordinate(lat, long, calculate_Height(square_size**2)))
    
    # Plot results
    plt.figure(figsize=(8, 8))
    plt.scatter(coords[:, 0], coords[:, 1], color='blue', label='Data Points')

    # Convex Hull
    hull = ConvexHull(coords)
    for simplex in hull.simplices:
        plt.plot(coords[simplex, 0], coords[simplex, 1], 'k--', label='Convex Hull' if simplex[0] == 0 else "")

    # Bounding Rectangle
    rect_corners = np.array([  
        center + extent[0] * axis[0] + extent[1] * axis[1],
        center + extent[0] * axis[0] - extent[1] * axis[1],
        center - extent[0] * axis[0] - extent[1] * axis[1],
        center - extent[0] * axis[0] + extent[1] * axis[1],
        center + extent[0] * axis[0] + extent[1] * axis[1]
    ])
    plt.plot(rect_corners[:, 0], rect_corners[:, 1], 'r-', label='Min Area Rectangle')

    # Drone Coverage Squares
    for drone_center in drone_centers:
        square_corners = np.array([
            drone_center + square_size * axis[0] + square_size * axis[1],
            drone_center + square_size * axis[0] - square_size * axis[1],
            drone_center - square_size * axis[0] - square_size * axis[1],
            drone_center - square_size * axis[0] + square_size * axis[1],
            drone_center + square_size * axis[0] + square_size * axis[1]
        ])
        plt.plot(square_corners[:, 0], square_corners[:, 1], 'g-', label="Drone Coverage" if drone_center[0] == drone_centers[0][0] else "")

    plt.legend()
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Drone Coverage Area")
    plt.grid()
    plt.show()

    return flyTo_coords

# Example usage
def generate_trajectory(start_x, start_y, steps=10, step_size=3):
    """Generates a vehicle trajectory with smooth movements."""
    trajectory = [Coordinate(start_x, start_y, 0)]
    
    for _ in range(steps - 1):
        # Move in a random direction with small increments
        delta_x = choice([-step_size, 0, step_size])
        delta_y = choice([-step_size, 0, step_size])
        
        new_x = max(0, min(20, trajectory[-1].lat + delta_x))
        new_y = max(0, min(20, trajectory[-1].lng + delta_y))
        
        trajectory.append(Coordinate(new_x, new_y, 0))
    
    return trajectory

# Generate multiple vehicle trajectories
coordslist = {
    "Vehicle_1": generate_trajectory(randint(0, 5), randint(0, 5), steps=10),
    "Vehicle_2": generate_trajectory(randint(5, 10), randint(5, 10), steps=10),
    "Vehicle_3": generate_trajectory(randint(10, 15), randint(10, 15), steps=10),
    "Vehicle_4": generate_trajectory(randint(15, 20), randint(15, 20), steps=10),
    "Vehicle_5": generate_trajectory(randint(0, 20), randint(0, 20), steps=10)
}

droneOrigin = Coordinate(0, 0, 0)
flyto = getDronesLoc(coordslist, droneOrigin)

