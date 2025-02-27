import communication_software.CoordinateHandler as CoordinateHandler
from communication_software.Communication import Communication
import asyncio
import time
import threading
from communication_software.frontendWebsocket import run_server
from communication_software.multiple_drone_optimization import getDronesLoc, calculate_Height_Distance
import communication_software.Interface as Interface
from communication_software.ROS import AtosCommunication

import rclpy

def main() -> None:

    Interface.print_welcome()
    if not rclpy.ok():
        print("Trying to initialize rclpy")
        rclpy.init()

    while True:
        #if this method returns true it means that the user wants to proceed
        if Interface.print_menu():
            ip = Interface.get_ip()

            #Try to get the coordinates from the ROS2 service
            ATOScommunicator = AtosCommunication()
            ATOScommunicator.publish_init()
            time.sleep(5)

            origo = ATOScommunicator.get_origin_coordinates()

                #Gets the trajectories for all of the objects
            ids = ATOScommunicator.get_object_ids()
            trajectoryList = {}
            for id in ids:
                coordlist = ATOScommunicator.get_object_traj(id)
                for coord in coordlist:
                    print(coord)
                trajectoryList[id] = coordlist

            droneOrigin, angle = CoordinateHandler.getNewDroneOrigin(trajectoryList,origo)

            #If the coordinate can not be found, None will be returned and the script will not continue
            if droneOrigin == None:
                print("Coordinates could not be found")
                continue
            #Create the handler for the communication. sendCoordinatesWebSocket starts a server that will run until it is stopped

            flyTo1, flyTo2, angle1, angle2 = getDronesLoc(trajectoryList,droneOrigin)
            print("FlyTo1:",flyTo1)
            print("FlyTo2:",flyTo2)
            print("angle1:",angle1)
            print("angle2:",angle2)

            start_server()

            communication = Communication()
            try:
                print("Server starting, press ctrl + c to exit")
                asyncio.run(communication.send_coordinates_websocket(coordinates=droneOrigin, angle=angle, ip=ip))
            except KeyboardInterrupt:
                print("The server was interrupted!")
                continue
            except OSError as e:
                print(e)

                continue
            except Exception as e:
                print(e)
                continue

        else:
            Interface.print_goodbye()
            break

if __name__ == "__main__":
    main()


def start_server():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("FastAPI server started in a separate thread!")