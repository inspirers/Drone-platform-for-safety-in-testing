import numpy as np

class Coordinate():
    """Coordinate class that contains an altitude, longutude and altitude
    """
    def __init__(self,lat:float,lng:float,alt:float) -> None:
        self.lat = lat
        self.lng = lng
        self.alt = alt

def addHeight(coordinate:Coordinate) -> Coordinate:
    height = calculateHeight()
    coordinate.alt = height
    return coordinate

def calculateHeight(area:int = 1500) -> int:
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
    
def getNewDroneOrigin(coordslist, droneOrigin) -> tuple[Coordinate,int]:
    """Returns the longitud, latitude, altitude and the angle the drone should rotate to for a 
    favourable position of the fov. Longitude and latitude is the mean x and y value of all objects 
    position throughout the test. Height is decided by the total area to cover and the angle by which 
    direction the test objets travel further to optimize for 16:9 resolution. 
    Args:
        coordslist (dictionary): The keys are the different object ids, values is their position throughout
        the test
        droneOrigin (Coordinate): The test origin

    Returns:
            flyTo (Coordinate): The longitude, latitude and altitude for the drone to fly to
            angle (int): the yaw rotation for the drone, relative to north 
    """
    
    max_x = [0,0]
    min_x = [0,0]
    max_y = [0,0]
    min_y = [0,0]
    x_sum = 0
    y_sum = 0
    coordinateCounter = 0
    for coordList in coordslist.values():
        for coord in coordList:
            y = coord.lat
            x = coord.lng
            x_sum += x
            y_sum += y
            coordinateCounter += 1

            if x > max_x[0]:
                max_x = [x,y]
            if y > max_y[1]:
                max_y = [x,y]
            if x < min_x[0]:
                min_x = [x,y]
            if y < min_y[1]:
                min_y = [x,y]

    x_travel = max_x[0]-min_x[0]
    y_travel = max_y[1]-min_y[1]
    x_distance = np.sqrt((x_travel)**2+(max_x[1]-min_x[1])**2)
    y_distance = np.sqrt((y_travel)**2+(max_y[1]-min_y[1])**2)

    if coordinateCounter != 0:
        x_origin_cartesian = x_sum / coordinateCounter
        y_origin_cartesian = y_sum / coordinateCounter

    # Earth radius in meters
    earth_radius = 6371000

    # Convert Cartesian displacements to angular displacements
    delta_latitude = x_origin_cartesian / earth_radius * (180 / np.pi)
    delta_longitude = y_origin_cartesian / (earth_radius * np.cos(droneOrigin.lat * np.pi / 180)) * (180 / np.pi)

    # Calculate new coordinates
    new_latitude = droneOrigin.lat + delta_latitude
    new_longitude = droneOrigin.lng + delta_longitude
    if x_travel >= y_travel:
        deltaY = np.abs(max_x[1]-min_x[1])
        angle = np.arctan2(deltaY,x_travel)
        angle = (angle - np.pi/2)*(180/np.pi)
    else:
        deltaX = np.abs(max_y[0]-min_y[0])
        angle = np.arctan2(deltaX,y_travel)
        angle = (angle)*(180/np.pi)
    
    x_distance_with_margin = x_distance + 4
    y_distance_with_margin = y_distance + 4

    area_to_be_covered = x_distance_with_margin * y_distance_with_margin
    height = calculateHeight(area_to_be_covered)
    flyTo = Coordinate(new_latitude,new_longitude,height)
    angle = round(angle)

    return flyTo, angle
