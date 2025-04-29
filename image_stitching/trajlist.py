class TrajList:
    """Class that represents the real time trajectory list for a certain object"""
    def __init__(self, id, coordlist): 
        self.id = id  
        self.trajlist = {} 
        self.trajlist[id] = coordlist
    
    def __str__(self):
        return f"TrajectoryList(id={self.id}, coordlist={self.trajlist})"

    def __repr__(self):
        return f"TrajectoryList(id={self.id}, coordlist={self.trajlist})"