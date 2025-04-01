import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from scipy.spatial import ConvexHull
from CoordinateHandler import Coordinate

def compute_convex_hull(points):
    """Compute the convex hull of a set of points."""
    hull = ConvexHull(points)
    return Polygon([points[i] for i in hull.vertices])

def can_fit_two_squares(polygon, square_size):
    """Check if two identical squares of size 'square_size' can fit inside the polygon."""
    minx, miny, maxx, maxy = polygon.bounds
    step = square_size / 10  # Small step for placement testing
    
    candidates = []
    
    for x in np.arange(minx, maxx - square_size, step):
        for y in np.arange(miny, maxy - square_size, step):
            square1 = box(x, y, x + square_size, y + square_size)
            if polygon.contains(square1):
                for x2 in np.arange(minx, maxx - square_size, step):
                    for y2 in np.arange(miny, maxy - square_size, step):
                        square2 = box(x2, y2, x2 + square_size, y2 + square_size)
                        if polygon.contains(square2) and square1.disjoint(square2):
                            return square1, square2  # Return as soon as we find two fitting squares
    return None, None

def find_largest_identical_squares(points):
    """Find the largest two identical squares that fit inside the convex hull."""
    convex_hull = compute_convex_hull(points)
    minx, miny, maxx, maxy = convex_hull.bounds
    max_possible_size = min(maxx - minx, maxy - miny) / 2  # Maximum starting square size
    
    # Binary search for max square size
    left, right = 0, max_possible_size
    best_squares = (None, None)
    
    while right - left > 0.01:  # Precision threshold
        mid_size = (left + right) / 2
        square1, square2 = can_fit_two_squares(convex_hull, mid_size)
        
        if square1 and square2:
            best_squares = (square1, square2)  # Store best result
            left = mid_size  # Try a larger square
        else:
            right = mid_size  # Reduce size
    
    return convex_hull, best_squares[0], best_squares[1]

def plot_results(points, convex_hull, square1, square2):
    """Plot the convex hull, two identical squares, and original points."""
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # Plot the original points
    points = np.array(points)
    ax.scatter(points[:, 0], points[:, 1], color='blue', label="Original Points")

    # Plot the convex hull
    hull_x, hull_y = convex_hull.exterior.xy
    ax.plot(hull_x, hull_y, 'k-', linewidth=2, label="Convex Hull")

    # Plot the first square
    if square1:
        x1, y1 = square1.exterior.xy
        ax.fill(x1, y1, color='red', alpha=0.5, label="Square 1")

    # Plot the second square
    if square2:
        x2, y2 = square2.exterior.xy
        ax.fill(x2, y2, color='green', alpha=0.5, label="Square 2")

    # Formatting
    ax.set_title("Largest Two Identical Squares in Convex Hull")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.legend()
    ax.set_aspect('equal')

    plt.show()

# Example: Set of points defining the convex hull

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

coords_list = []
for coordinate in coords.values():
    coords_list.append([coordinate.lat, coordinate.lng])
    
points = np.array(coords_list)

convex_hull, square1, square2 = find_largest_identical_squares(points)

# Plot the results
plot_results(points, convex_hull, square1, square2)
