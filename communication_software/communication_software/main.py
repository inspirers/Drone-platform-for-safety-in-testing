import communication_software.CoordinateHandler as CoordinateHandler
from communication_software.Communication import Communication
import asyncio
import time
import threading
from communication_software.frontendWebsocket import run_server
from communication_software.multiple_drone_optimization import getDronesLoc
import communication_software.Interface as Interface
from communication_software.ROS import AtosCommunication

import rclpy

def main() -> None:
    Interface.print_welcome()
    if not rclpy.ok():
        print("Trying to initialize rclpy")
        rclpy.init()

    ATOScommunicator = AtosCommunication()  
    try:
        while True:
            #if this method returns true it means that the user wants to proceed
            if Interface.print_menu():
                ip = Interface.get_ip()

                #Try to get the coordinates from the ROS2 service
                ATOScommunicator.publish_init()
                time.sleep(5)

                origo = ATOScommunicator.get_origin_coordinates()

                    #Gets the trajectories for all of the objects
                ids = ATOScommunicator.get_object_ids()
                trajectoryList = {}
                for id in ids:
                    coordlist = ATOScommunicator.get_object_traj(id)
                    trajectoryList[id] = coordlist

                droneOrigin, angle = CoordinateHandler.getNewDroneOrigin(trajectoryList,origo)

                #If the coordinate can not be found, None will be returned and the script will not continue
                if droneOrigin == None:
                    print("Coordinates could not be found")
                    continue
                #Create the handler for the communication. sendCoordinatesWebSocket starts a server that will run until it is stopped
                flyTo1, flyTo2, angle1, angle2 = getDronesLoc(trajectoryList,droneOrigin)
                print(f"Drone going to: \n {flyTo1}, angle1: {angle1} \n {flyTo2}, angle1: {angle2}")
                
                droneOrigins = flyTo1,flyTo2
                angles = angle1,angle2
                
                if len(droneOrigins) != len(angles):
                    print("Mismatch in the number of drone origins and angles.")
                    continue
                
                start_server(ATOScommunicator)

                communication = Communication()
                try:
                    print("Server starting, press ctrl + c to exit")
                    asyncio.run(communication.send_coordinates_websocket(ip=ip, droneOrigins=droneOrigins, angles=angles)) 
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
    finally:
        ATOScommunicator.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()


def start_server(atos_communicator):
    server_thread = threading.Thread(target=run_server, args=(atos_communicator,), daemon=True)
    server_thread.start()
    print("FastAPI server started in a separate thread!")