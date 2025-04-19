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

    def are_colinear(points, tol=1e-9):
        if len(points) < 3:
            return True

        x0, y0 = points[0]
        x1, y1 = points[1]
        for x, y in points[2:]:
            cp = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
            if abs(cp) > tol:
                return False
        return True

    if are_colinear(coords):
        rect = Rectangle()
        rect.center = np.mean(coords, axis=0)
    
        sorted_coords = sorted(coords, key=lambda p: p[0])  # For sorting by x-coordinate
    
        start_coord = sorted_coords[0]
        end_coord = sorted_coords[-1]

        direction = (end_coord) - rect.center

        U0 = normalize(direction)
        U1 = perp(U0) 

        extent_long = np.linalg.norm(direction)
        rect.extent[1] = extent_long/2
        rect.extent[0] = extent_long
        rect.axis[0] = U0
        rect.axis[1] = U1
        rect.area = 4*rect.extent[0]*rect.extent[1]
    else:
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
        print("Can not ensure full coverage with current drone amount")

    flyTo_coords = []
    for drone_center in drone_centers:
        drone_loc_x = drone_center[0]
        drone_loc_y = drone_center[1]

        delta_lat = drone_loc_x / 6371000 * (180 / np.pi)
        delta_long = (drone_loc_y / (6371000 * np.cos(droneOrigin.lat * np.pi / 180))) * (180 / np.pi)
        
        lat = droneOrigin.lat + delta_lat
        long = droneOrigin.lng + delta_long
        
        flyTo_coords.append(Coordinate(lat, long, height))

    split_angle_radians = np.arctan2(split_axis[1], split_axis[0])
    angle = np.degrees(split_angle_radians) + 90

    return flyTo_coords, angle
