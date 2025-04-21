import os
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

# --- NEW async wrapper function ---
async def run_comm_server(communication: Communication, ip: str, droneOrigins: list, angles: list):
    loop = asyncio.get_running_loop()
    communication.loop = loop  

    communication.start_redis_listener_thread()

    await communication.send_coordinates_websocket(ip=ip, droneOrigins=droneOrigins, angles=angles)

def main() -> None:
    Interface.print_welcome()
    if not rclpy.ok():
        print("Trying to initialize rclpy")
        rclpy.init()

    ATOScommunicator = AtosCommunication()
    try:
        while True:
            if Interface.print_menu():
                ip = Interface.get_ip()
                ATOScommunicator.publish_init()
                time.sleep(1) 

                origo = get_origo_coords(ATOScommunicator)

                ids = ATOScommunicator.get_object_ids()
                trajectoryList = {}
                for id in ids:
                    coordlist = ATOScommunicator.get_object_traj(id)
                    trajectoryList[id] = coordlist

                droneOrigin, angle = CoordinateHandler.getNewDroneOrigin(trajectoryList, origo) 

                if droneOrigin is None:
                    print("Coordinates could not be found")
                    continue

                flyTo1, flyTo2, angle1, angle2, total_overlap = getDronesLoc(trajectoryList, droneOrigin) 
                print(f"Drone going to: \n {flyTo1}, angle1: {angle1} \n {flyTo2}, angle2: {angle2}, estimated overlap: {total_overlap}")

                droneOrigins = [flyTo1, flyTo2] 
                angles = [angle1, angle2]       

                if len(droneOrigins) != len(angles):
                    print("Mismatch in the number of drone origins and angles.")
                    continue

                start_server(ATOScommunicator) 

                communication = Communication()

                try:
                    print("Communication server starting, press ctrl + c to exit")
                    asyncio.run(run_comm_server(communication, ip=ip, droneOrigins=droneOrigins, angles=angles))
                except KeyboardInterrupt:
                    print("\nCommunication server interrupted!")
                    if communication.redis_listener_task and communication.redis_listener_task.is_alive():
                         communication.redis_listener_stop_event.set()
                         communication.redis_listener_task.join(timeout=2)
                    continue 
                except OSError as e:
                    print(f"OS Error starting server: {e}")
                    continue
                except Exception as e:
                    print(f"Unexpected error starting server: {e}")
                    continue

            else:
                Interface.print_goodbye()
                break
    finally:
        # Graceful shutdown
        print("Shutting down ROS node...")
        if ATOScommunicator:
             ATOScommunicator.destroy_node()
        if rclpy.is_initialized():
            rclpy.shutdown()
        print("Shutdown complete.")


def start_server(atos_communicator):
    server_thread = threading.Thread(target=run_server, args=(atos_communicator,), daemon=True)
    server_thread.start()
    print("FastAPI server started in a separate thread!")

def get_origo_coords(ATOScommunicator) -> CoordinateHandler.Coordinate:
    altitude = os.getenv("ENV_ALTITUDE")
    latitude = os.getenv("ENV_LATITUDE")
    longitude = os.getenv("ENV_LONGITUDE")
    if altitude and latitude and longitude and is_debug_mode():
        print("Using custom coords")
        return CoordinateHandler.Coordinate(lat=float(latitude),lng=float(longitude),alt=float(altitude))
    return  ATOScommunicator.get_origin_coordinates()


def is_debug_mode():
    """
    Retrieves the DEBUG_MODE environment variable and returns it as a boolean.
    Handles various string representations of boolean values.
    """
    debug_mode_str = os.getenv("DEBUG_MODE", "false").lower() # default to "false" if not set

    if debug_mode_str in ("true", "1", "t", "y", "yes"):
        return True
    elif debug_mode_str in ("false", "0", "f", "n", "no", ""):
        return False
    else:
        print(f"Warning: Invalid DEBUG_MODE value: {debug_mode_str}.  Treating as false.")
        return False

if __name__ == "__main__":
    main()