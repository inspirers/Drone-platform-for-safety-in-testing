import websockets
from communication_software.CoordinateHandler import Coordinate

class Communication():
    """Class that handles all communication. It takes in an IP-adress, starts 
    a websocket server, handles communication with the client and handles communication with a MQTT broker.
    with a websocket client and MQTT broker
    """
    
    def __init__(self) -> None:
        self.lat = 0
        self.lng = 0
        self.alt = 0
        self.connections = set()

    async def send_coordinates_websocket(self, coordinates:Coordinate, angle:int, ip:str) -> None:
        """Script for starting the server and letting the user know that the server has been started,
        keeps the server on until interrupted
        """
        # Only keep the first 10 characters
        self.lat = str(coordinates.lat)[0:9]
        self.lng = str(coordinates.lng)[0:9]
        self.alt = str(coordinates.alt)[0:2]
        self.angle = str(angle)

        server = await websockets.serve(self.webs_server, ip, 14500)
        print("WebSocket server started.")
        await server.wait_closed()

    async def webs_server(self,ws: websockets.WebSocketServerProtocol) -> None:
        """The method that is called when the client is connected,

        Args:
            ws (websockets.WebSocketServerProtocol): The connection
        """
        print("Client connected.")
        print(ws.remote_address[0])
        self.connections.add(ws)
        
        try:
            while True:
                
                data = await ws.recv()
                
                # Do something with the received frame, for example, save it to a file
                await self.on_message(data)   

        except websockets.exceptions.ConnectionClosedError:
            print("Client disconnected.")

    async def on_message(self, frame: websockets.Data) -> None:
        """If message is received and the client requests the coordinates, the coordinates will be sent.
        Otherwise, the message will just be printed.

        Args:
            frame (websockets.Data): the recived data
        """
        print(f"Received: {frame}")
        if frame == "REQ/COORDS":
            await self.send_coords()
        else:
            
            print("Received frame with size:", len(frame))
            print(f"{frame}")

    async def send_coords(self) -> None:
        """Send the coordinates stored in the to the 
        """
        for connection in self.connections:
            message = f"COORDS/{self.lat}/{self.lng}/{self.alt}/{self.angle}"
            await connection.send(message)
            print(f"Sent: {message}")