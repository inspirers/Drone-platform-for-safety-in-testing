import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
from CoordinateHandler import Coordinate

def calculate_Height_Distance(area:int = 1500, d_decrease:float = 1.5, h_increase:float = 1.4) -> int:
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
    
    height = round(height)*h_increase #no need for decimals

    d = round((2*radius*np.cos(alpha))/d_decrease) 

    total_overlap = 2*(radius)*np.cos(alpha)/d

    if d < 2:
        d = 2

    print("Drone distance: ", d, " m")
    if height < 100:  # swedish regulation limits the drone flying height to below 120 m
        return height, d
    else:
        print("The height exceeds swedish regulations")
        height = 99
        return height, d, total_overlap

coords = {
    "veh_501": Coordinate(-10.0, 15.5, 0),
    "veh_502": Coordinate(5.2, -10.3, 0),
    "veh_503": Coordinate(-15.3, 8.4, 0),
    "veh_504": Coordinate(12.0, -4.7, 0),
    "veh_505": Coordinate(-8.1, 13.3, 0),
    "veh_506": Coordinate(16.5, -19.0, 0),
    "veh_507": Coordinate(-2.4, 2.2, 0),
    "veh_508": Coordinate(10.8, -11.5, 0),
    "veh_509": Coordinate(-5.0, 19.9, 0),
    "veh_510": Coordinate(20.0, 5.0, 0),
    "veh_511": Coordinate(-12.3, -6.6, 0),
    "veh_512": Coordinate(0.0, 14.2, 0),
    "veh_513": Coordinate(-17.4, 9.5, 0),
    "veh_514": Coordinate(4.6, -18.1, 0),
    "veh_515": Coordinate(-20.0, -2.0, 0),
    "veh_516": Coordinate(15.0, 0.0, 0),
    "veh_517": Coordinate(-9.9, 17.8, 0),
    "veh_518": Coordinate(18.5, -14.3, 0),
    "veh_519": Coordinate(-6.4, 3.3, 0),
    "veh_520": Coordinate(11.1, -7.2, 0),
}
droneOrigin =  Coordinate(37.7749, -122.4194, 0)

def getDronesLoc(coordslist: dict[Coordinate], droneOrigin: Coordinate) -> tuple[Coordinate]:
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
    coords_list = []
    for coordinate in coordslist.values():
        coords_list.append([coordinate.lat, coordinate.lng])
    
    coords_list = np.array(coords_list)
    convex_hull = ConvexHull(coords_list)
    plt.plot(coords_list[:,0], coords_list[:,1], 'o')

    for simplex in convex_hull.simplices:
        plt.plot(coords_list[simplex, 0], coords_list[simplex, 1], 'k-')

    mass_centroid = np.mean(coords_list, axis=0)

    plt.scatter(mass_centroid[0], mass_centroid[1], color = "red")

    plt.show()


getDronesLoc(coords, droneOrigin)