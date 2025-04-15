import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
from scipy import optimize
from random import randint, choice

class Coordinate:
    def __init__(self, lat, lng, alt=0):
        self.lat = lat
        self.lng = lng
        self.alt = alt

def calculate_Height(area):
    """Calculates the height that the drone need to fly at to cover a certain area 
    Args:
        area (int): Which currently is preset to 1500, unit: m^2

    Returns:
            height (int): The height to fly at, unit: m 
    """
    #area = the FOV area to be covered in m^2
    theta = (82.6/2)*(np.pi/180) #chalmers drone has a lens of 82.6 degrees, convert to rad
    x = np.sqrt(area/(16*9)) #FOV is 16:9 resolution 
    y = (16*x)/4 #Photosensor is 4:3 resolution
    radius = np.sqrt((2*y)**2+(1.5*y)**2) #pythagoras theorem
    height = radius / np.tan(theta) 
    height = round(height) #no need for decimals
    if height < 99: #swedish regulation limits the drone flying height to below 120 m
        return height 
    else:
        print("The height exceeds swedish regulations")
        height = 99
        return height

class ProximityError(Exception):

    def __init__(self, message="Does not take more than one drone and overlap over 90 percent"):
        super().__init__(message)

def getDronesLoc(coordslist, droneOrigin, n_drones=2, overlap=0.5):

    if n_drones >= 2 and overlap > 0.9:
        raise ProximityError
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

    def min_area_rectangle_of_hull(polygon): # takes convex hull as input
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
    
    # Define the starting and stopping sizes
    longer_extent = max(extent)
    shorter_extent = min(extent)
    square_size = longer_extent

    if extent[0] > extent[1]:
        split_axis = axis[0]
    else:
        split_axis = axis[1]
    
    step = 0.98  # reduction factor per loop
    split_offset = float("inf")
    iter = 0

    if n_drones >= 2:         
        while split_offset*n_drones+split_offset >= longer_extent*2*1.1:
            iter += 1
            if iter >= 99:
                print("Max iterations reached")
                break
            square_size *= step
            split_offset = (square_size * (1 - overlap) * 2) 
        drone_centers = [center + (i - (n_drones - 1) / 2) * split_offset * split_axis for i in range(n_drones)]
        
        if square_size <= shorter_extent:
            square_size = shorter_extent*1.1
            split_offset = (square_size * (1 - overlap) * 2)
            drone_centers = [center + (i - (n_drones - 1) / 2) * split_offset * split_axis for i in range(n_drones)] 
    
    if n_drones == 1: 
        square_size = 1.1*longer_extent
        drone_centers = [center]

    height = calculate_Height((2*square_size)**2)

    if height < 30:
        height = 30
        square_size = optimize.root_scalar(lambda x: calculate_Height(x)-height, x0=20, method="newton").root
        split_offset = (square_size * (1 - overlap) * 2)
        drone_centers = [center + (i - (n_drones - 1) / 2) * split_offset * split_axis for i in range(n_drones)] 

    if height == 99:
        height = 99
        square_size = optimize.root_scalar(lambda x: calculate_Height(x)-height, x0=20, method="newton").root
        split_offset = (square_size * (1 - overlap) * 2)
        drone_centers = [center + (i - (n_drones - 1) / 2) * split_offset * split_axis for i in range(n_drones)] 
        print("Can not ensure full coverage with same drone amount")

    
    # Reduce square size 
    
    flyTo_coords = []
    for drone_center in drone_centers:
        drone_loc_x = drone_center[0]
        drone_loc_y = drone_center[1]

        delta_lat = drone_loc_x / 6371000 * (180 / np.pi)
        delta_long = (drone_loc_y / (6371000 * np.cos(droneOrigin.lat * np.pi / 180))) * (180 / np.pi)
        
        lat = droneOrigin.lat + delta_lat
        long = droneOrigin.lng + delta_long
        
        flyTo_coords.append(Coordinate(lat, long, height))
    
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
    plt.quiver(center[0], center[1], axis[0][0], axis[0][1], angles='xy', scale_units='xy', scale=1, color='magenta', label='Axis 0')
    plt.quiver(center[0], center[1], axis[1][0], axis[1][1], angles='xy', scale_units='xy', scale=1, color='cyan', label='Axis 1')
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Drone Coverage Area")
    plt.grid()
    plt.axis('equal')
    plt.show()

    split_angle_radians = np.arctan2(split_axis[1], split_axis[0])
    angle = np.degrees(split_angle_radians) + 90

    return flyTo_coords, angle

# Example usage
def generate_trajectory(start_x, start_y, steps=10, step_size=3):
    """Generates a vehicle t§rajectory with smooth movements."""
    trajectory = [Coordinate(start_x, start_y, 0)]
    
    for _ in range(steps - 1):
        # Move in a random direction with small increments
        delta_x = choice([-step_size, 0, step_size])
        delta_y = choice([-step_size, 0, step_size])
        
        new_x = max(0, min(100, trajectory[-1].lat + delta_x))
        new_y = max(0, min(100, trajectory[-1].lng + delta_y))
        
        trajectory.append(Coordinate(new_x, new_y, 0))
    
    return trajectory

# Generate multiple vehicle trajectories
coordslist = {
    "Vehicle_1": generate_trajectory(randint(0, 100), randint(0, 100), steps=10),
    "Vehicle_2": generate_trajectory(randint(0, 100), randint(0, 100), steps=10),
    "Vehicle_3": generate_trajectory(randint(0, 100), randint(0, 100), steps=10),
    "Vehicle_4": generate_trajectory(randint(0, 100), randint(0, 100), steps=10),
    "Vehicle_5": generate_trajectory(randint(0, 100), randint(0, 100), steps=10)
}

droneOrigin = Coordinate(0, 0, 0)
flyto = getDronesLoc(coordslist, droneOrigin)

