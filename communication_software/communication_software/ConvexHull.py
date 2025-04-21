import numpy as np
from scipy.spatial import ConvexHull
import matplotlib.pyplot as plt

class Coordinate():
    """Coordinate class that contains an altitude, longutude and altitude
    """
    def __init__(self,lat:float,lng:float,alt:float) -> None:
        self.lat = lat
        self.lng = lng
        self.alt = alt
    
    def __str__(self):
        return f"Coordinate(lat={self.lat}, lng={self.lng}, alt={self.alt})"
    
    def __repr__(self):
        return f"Coordinate(lat={self.lat}, lng={self.lng}, alt={self.alt})"

def calculate_Height(area:int = 1500) -> int:
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
    if height < 100: #swedish regulation limits the drone flying height to below 120 m
        return height 
    else:
        print("The height exceeds swedish regulations")
        height = 99
        return height

def getDronesLoc(coordslist, droneOrigin):

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

    # Compute the four corners of the rectangle
    rect_corners = np.array([
        center + extent[0] * axis[0] + extent[1] * axis[1],
        center + extent[0] * axis[0] - extent[1] * axis[1],
        center - extent[0] * axis[0] - extent[1] * axis[1],
        center - extent[0] * axis[0] + extent[1] * axis[1],
        center + extent[0] * axis[0] + extent[1] * axis[1]  # Close the rectangle
    ])

    # Adjust overlap parameter O, where O=0 means no overlap, and O=1 means full overlap
    O = 0.2  # You can change this to any value between 0 and 1 to test different overlaps

    # Determine the longer side
    longer_extent = max(extent)

    # Compute the square size based on the longer extent to ensure full coverage
    # The square's side length needs to be at least the longer extent of the rectangle
    square_size = longer_extent

    # Compute the overlap and offset for the two squares
    split_offset = (1 - O) * longer_extent  # This determines how much the squares are shifted
    split_axis = axis[0] if extent[0] > extent[1] else axis[1]

    split_angle_radians = np.arctan2(split_axis[1], split_axis[0])
    angle = np.degrees(split_angle_radians) + 90

    # Calculate the centers of the two squares
    square1_center = center - split_offset / 2 * split_axis
    square2_center = center + split_offset / 2 * split_axis

    # Compute the four corners of the two squares
    square1_corners = np.array([
        square1_center + square_size * axis[0] + square_size * axis[1],
        square1_center + square_size * axis[0] - square_size * axis[1],
        square1_center - square_size * axis[0] - square_size * axis[1],
        square1_center - square_size * axis[0] + square_size * axis[1],
        square1_center + square_size * axis[0] + square_size * axis[1]
    ])

    square2_corners = np.array([
        square2_center + square_size * axis[0] + square_size * axis[1],
        square2_center + square_size * axis[0] - square_size * axis[1],
        square2_center - square_size * axis[0] - square_size * axis[1],
        square2_center - square_size * axis[0] + square_size * axis[1],
        square2_center + square_size * axis[0] + square_size * axis[1]
    ])

    drone_loc_x1 = square1_center[0]
    drone_loc_y1 = square1_center[1]

    drone_loc_x2 = square2_center[0]
    drone_loc_y2 = square2_center[1]

    #Plot everything
    plt.figure()
    plt.scatter(coords[:, 0], coords[:, 1], label="Input Points", color="blue")
    plt.scatter(center[0], center[1], label="Center", color="red")
    plt.scatter(drone_loc_x1, drone_loc_y1, marker="x")
    plt.scatter(drone_loc_x2, drone_loc_y2, marker="x")
    plt.plot(rect_corners[:, 0], rect_corners[:, 1], label="Min Area Rectangle", color="black")
    plt.plot(square1_corners[:, 0], square1_corners[:, 1], label="Square 1", color="green")
    plt.plot(square2_corners[:, 0], square2_corners[:, 1], label="Square 2", color="purple")
    plt.legend()
    plt.show()
    
    # Earth radius in meters
    earth_radius = 6371000

    # Convert Cartesian displacements to angular displacements
    delta_lat1 = drone_loc_x1 / earth_radius * (180 / np.pi)
    delta_long1 = (
        drone_loc_y1
        / (earth_radius * np.cos(droneOrigin.lat * np.pi / 180))
        * (180 / np.pi)
    )

    # Convert Cartesian displacements to angular displacements
    delta_lat2 = drone_loc_x2 / earth_radius * (180 / np.pi)
    delta_long2 = (
        drone_loc_y2
        / (earth_radius * np.cos(droneOrigin.lat * np.pi / 180))
        * (180 / np.pi)
    )

    # Calculate new coordinates
    lat1 = droneOrigin.lat + delta_lat1
    long1 = droneOrigin.lng + delta_long1

    lat2 = droneOrigin.lat + delta_lat2
    long2 = droneOrigin.lng + delta_long2

    area = square_size**2

    height = calculate_Height(area)

    flyTo1 = Coordinate(lat1, long1, height)
    flyTo2 = Coordinate(lat2, long2, height)

    return flyTo1, flyTo2, round(angle)