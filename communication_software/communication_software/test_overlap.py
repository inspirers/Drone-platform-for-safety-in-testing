import numpy as np

def parametrized_function(h_increase: float, d_decrease: float, area=500):

    if h_increase == 0  or d_decrease == 0:
        raise ZeroDivisionError("Can not take overlap == 0")

    #area = the FOV area to be covered in m^2
    alpha = np.arctan(9/16)
    theta = (82.6/2)*(np.pi/180) #chalmers drone has a lens of 82.6 degrees, convert to rad
    x = np.sqrt(area/(16*9)) #FOV is 16:9 resolution 
    y = (16*x)/4 #Photosensor is 4:3 resolution
    radius = np.sqrt((2*y)**2+(1.5*y)**2) #pythagoras theorem
    height = radius / np.tan(theta) 
    
    h = round(height)*h_increase #no need for decimals

    d = round((2*radius*np.cos(alpha))/d_decrease) 
    
    return d, h, (2*(radius)*np.cos(alpha))/d

print(parametrized_function(1.4, 1.5))


