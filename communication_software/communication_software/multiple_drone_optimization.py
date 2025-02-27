   
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
from communication_software.CoordinateHandler import Coordinate

def calculate_Height_Distance(area:int = 1500) -> int:
    """Calculates the height that the drone need to fly at to cover a certain area 
    Args:
        area (int): Which currently is preset to 1500, unit: m^2

    Returns:
            height (int): The height to fly at, unit: m 
    """
    
    #area = the FOV area to be covered in m^2
    alpha = np.arctan(9/16)
    theta = (82.6/2)*(np.pi/180) #chalmers drone has a lens of 82.6 degrees, convert to rad
    x = np.sqrt(area/(16*9)) #FOV is 16:9 resolution 
    y = (16*x)/4 #Photosensor is 4:3 resolution
    radius = np.sqrt((2*y)**2+(1.5*y)**2) #pythagoras theorem
    height = radius / np.tan(theta) 
    height = round(height) #no need for decimals

    # distance

    d = 2*np.cos(alpha)*height*np.tan(theta/2)

    if height < 100: #swedish regulation limits the drone flying height to below 120 m
        return height, d
    else:
        print("The height exceeds swedish regulations")
        height = 99
        return height, d

def getDronesLoc(coordslist, droneOrigin):
    """Returns the longitud, latitude, altitude and the angle the drone should rotate to for a 
    favourable position of the fov. Longitude and latitude is the mean x and y value of all objects 
    position throughout the test. Height is decided by the total area to cover and the angle by which 
    direction the test objets travel further to optimize for 16:9 resolution. 
    Args:
        coordslist (dictionary): The keys are the different object ids, values is their position throughout
        the test (in ATOS internal cartesian coordinate plane?)
        droneOrigin (Coordinate): The test origin in (lat, long?)

    Returns:
            flyTo (Coordinate): The longitude, latitude and altitude for the drone to fly to
            angle (int): the yaw rotation for the drone, relative to north 
    """
    
    _, sample_coord_set = next(iter(coordslist.items()))
    sample_coord = next(iter(sample_coord_set))
    max_x = [sample_coord.lat, sample_coord.lng]
    max_y = [sample_coord.lat, sample_coord.lng]
    min_x = [sample_coord.lat, sample_coord.lng]
    min_y = [sample_coord.lat, sample_coord.lng]

    for coordList in coordslist.values():
        for coord in coordList:
            
            x = coord.lat
            y = coord.lng
            
            if x > max_x[0]:
                max_x = [x,y]
            if y > max_y[1]:
                max_y = [x,y]
            if x < min_x[0]:
                min_x = [x,y]
            if y < min_y[1]:
                min_y = [x,y]

    p_cart = np.array([max_x, max_y, min_x, min_y])
    p1 = p_cart[0]
    p2 = p_cart[1]
    p3 = p_cart[2]
    p4 = p_cart[3]
    print("p-cart values:", p_cart)

    #   Segment the area through iteration for two parts equal in area
    # Define function for iterating to divide the area by two

    # Function for area by shoelace method

    def shoelace_area(p1, p2, p3, p4):



        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        
        area = 0.5 * abs(
            (x1 * y2 + x2 * y3 + x3 * y4 + x4 * y1) - 
            (y1 * x2 + y2 * x3 + y3 * x4 + y4 * x1)
        )
        
        return area

    # Define vertices functions and x vectors

    def vert1(x):
        return (p4[1] - p1[1])/(p4[0] - p1[0])*x + p1[1] - p1[0]*(p4[1] - p1[1])/(p4[0] - p1[0])
    def vert2(x):
        return (p2[1] - p1[1])/(p2[0] - p1[0])*x + p1[1] - p1[0]*(p2[1] - p1[1])/(p2[0] - p1[0])
    def vert3(x):
        print("p2[0]: ", p2[0])
        print("p2[1]: ", p2[1])
        print("p3[0]: ", p3[0])
        print("p3[1]: ", p3[1])
        return (p3[1] - p2[1])/(p3[0] - p2[0])*x + p2[1] - p2[0]*(p3[1] - p2[1])/(p3[0] - p2[0])
    def vert4(x):
        return (p3[1] - p4[1])/(p3[0] - p4[0])*x + p4[1] - p4[0]*(p3[1] - p4[1])/(p3[0] - p4[0])

    x_lin1 = np.linspace(p4[0], p1[0], 30)
    x_lin2 = np.linspace(p2[0], p1[0], 30)
    x_lin3 = np.linspace(p3[0], p2[0], 30)
    x_lin4 = np.linspace(p3[0], p4[0], 30)

    # Iterate for area

    target_area = shoelace_area(p1, p2, p3, p4)/2
    print("Target area:", target_area)

    for x2 in x_lin2:
        dp2 = np.array([x2, vert2(x2)])
        middle_x4 = x_lin4[len(x_lin4) // 2]
        dp4 = np.array([middle_x4, vert4(middle_x4)])
        area = shoelace_area(p1, dp2, p3, dp4)
        print("area: ", area)
        print("dp2: ", dp2)
        print("dp4: ", dp4)
        print("middle_x4: ", middle_x4)
        #print(area, target_area)
        if abs(area-(target_area)) < 10:
            break
    
    distance_2_4 = np.linalg.norm(dp2 - dp4)

    for x1 in x_lin1:
        dp1 = np.array([x1, vert1(x1)])
        middle_x3 = x_lin3[len(x_lin3) // 2]
        dp3 = np.array([middle_x3, vert3(middle_x3)])
        area = shoelace_area(dp1, p2, dp3, p4)
        #print(area, target_area)
        if abs(area-(target_area)) < 10:
            break

    distance_1_3 = np.linalg.norm(dp1 - dp3)

    # add area for margin
    print("Current area: ", area)
    height, drone_distance = calculate_Height_Distance(area + area/5)
    
    x_dl24 = np.linspace(dp2[0], dp4[0], 10)
    def drone_line_2_4(x):
        return (dp4[1] - dp2[1])/(dp4[0] - dp2[0])*x + dp2[1] - dp2[0]*(dp4[1] - dp2[1])/(dp4[0] - dp2[0])

    x_dl13 = np.linspace(dp1[0], dp3[0], 10)
    def drone_line_1_3(x):
        return (dp3[1] - dp1[1])/(dp3[0] - dp1[0])*x + dp1[1] - dp1[0]*(dp3[1] - dp1[1])/(dp3[0] - dp1[0])

    # DEFINE TEST ORIGIN IN CART COORDINATES

    # Define the function to find the root of (f1(x) - f2(x) = 0)
    def intersection(x):
        return drone_line_1_3(x) - drone_line_2_4(x)

    # Use fsolve to find the x-coordinate of the intersection
    x_origin = fsolve(intersection, 5)[0]  # 0 is an initial guess
    y_origin = drone_line_1_3(x_origin)  # Get corresponding y value

    # DEFINE DRONE POSITIONS IN CART COORDINATES

    def find_drone_point_1_3(x, y, d):
    
        # Compute the slope of the line
        delta_x = 1e-6  # Small step to approximate derivative
        m = (drone_line_1_3(x + delta_x) - drone_line_1_3(x)) / delta_x

        # Compute change in x using the distance formula
        dx = d / np.sqrt(1 + m**2)  # Adjust for slope
        x_new1 = x_origin + dx
        x_new2 = x_origin - dx  # Two possible points

        # Compute corresponding y-values
        y_new1 = drone_line_1_3(x_new1)
        y_new2 = drone_line_1_3(x_new2)

        return x_new1, y_new1, x_new2, y_new2  # Two possible points

    def find_drone_point_2_4(x, y, d):
    
        # Compute the slope of the line
        delta_x = 1e-6  # Small step to approximate derivative
        m = (drone_line_2_4(x + delta_x) - drone_line_2_4(x)) / delta_x

        # Compute change in x using the distance formula
        dx = d / np.sqrt(1 + m**2)  # Adjust for slope
        x_new1 = x_origin + dx
        x_new2 = x_origin - dx  # Two possible points

        # Compute corresponding y-values
        y_new1 = drone_line_2_4(x_new1)
        y_new2 = drone_line_2_4(x_new2)

        return x_new1, y_new1, x_new2, y_new2  # Two possible points

    drone_loc_x1, drone_loc_y1, drone_loc_x2, drone_loc_y2 = find_drone_point_2_4(x_origin, y_origin, drone_distance/2)

    # DEFINE DEFINE DRONE POSITIONS IN LATITUDE AND LONGITUDE
    
    # Earth radius in meters
    earth_radius = 6371000

    # Convert Cartesian displacements to angular displacements
    delta_lat1 = drone_loc_x1 / earth_radius * (180 / np.pi)
    delta_long1 = drone_loc_y1 / (earth_radius * np.cos(droneOrigin.lat * np.pi / 180)) * (180 / np.pi)

    # Convert Cartesian displacements to angular displacements
    delta_lat2 = drone_loc_x2 / earth_radius * (180 / np.pi)
    delta_long2 = drone_loc_y2 / (earth_radius * np.cos(droneOrigin.lat * np.pi / 180)) * (180 / np.pi)

    # Calculate new coordinates
    lat1 = droneOrigin.lat + delta_lat1
    long1 = droneOrigin.lng + delta_long1

    lat2 = droneOrigin.lat + delta_lat2
    long2 = droneOrigin.lng + delta_long2

    flyTo1 = Coordinate(lat1,long1,height)
    flyTo2 = Coordinate(lat2,long2, height)

   # BUILD ANGLE CALCULATION

    # Calculate angle for drone 1
    x_travel1 = max_x[0] - min_x[0]
    y_travel1 = max_y[1] - min_y[1]
    if x_travel1 >= y_travel1:
        deltaY1 = np.abs(max_x[1] - min_x[1])
        angle1 = np.arctan2(deltaY1, x_travel1)
        angle1 = (angle1 - np.pi/2) * (180/np.pi)
    else:
        deltaX1 = np.abs(max_y[0] - min_y[0])
        angle1 = np.arctan2(deltaX1, y_travel1)
        angle1 = (angle1) * (180/np.pi)
    angle1 = round(angle1)

    # Calculate angle for drone 2
    x_travel2 = max_x[0] - min_x[0]
    y_travel2 = max_y[1] - min_y[1]
    if x_travel2 >= y_travel2:
        deltaY2 = np.abs(max_x[1] - min_x[1])
        angle2 = np.arctan2(deltaY2, x_travel2)
        angle2 = (angle2 - np.pi/2) * (180/np.pi)
    else:
        deltaX2 = np.abs(max_y[0] - min_y[0])
        angle2 = np.arctan2(deltaX2, y_travel2)
        angle2 = (angle2) * (180/np.pi)
    angle2 = round(angle2)
    
    

    return flyTo1, flyTo2, angle1, angle2





