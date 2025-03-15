package com.dji.sdk.sample;

import com.MAVLink.common.msg_command_long;
import com.MAVLink.enums.MAV_CMD;
import com.MAVLink.MAVLinkPacket;
import com.MAVLink.common.msg_mission_item;



import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;

public class MAVLinkStarter {

    private DatagramSocket socket;
    private InetAddress droneAddress;
    private int dronePort = 14550;  // Default MAVLink UDP Port
    private int sequence = 0;  // MAVLink sequence number

    public MAVLinkStarter(String droneIp) {
        try {
            socket = new DatagramSocket();
            droneAddress = InetAddress.getByName(droneIp);  // Set drone IP
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void sendMAVLinkCommand(int commandType, float param1) {
        msg_command_long command = new msg_command_long();
        command.target_system = 1;  // Target system (1 = main autopilot)
        command.target_component = 1;  // Target component (1 = autopilot)
        command.command = commandType;
        command.param1 = param1;
        command.confirmation = 0;

        // Pack MAVLink message
        MAVLinkPacket packet = command.pack();

        try {
            byte[] encodedMessage = packet.encodePacket(); // Encode into bytes
            DatagramPacket udpPacket = new DatagramPacket(encodedMessage, encodedMessage.length, droneAddress, dronePort);
            socket.send(udpPacket);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
    public void sendMAVLinkCommand(msg_command_long command) {
        try {
            MAVLinkPacket packet = command.pack();
            byte[] encodedMessage = packet.encodePacket();
            DatagramPacket udpPacket = new DatagramPacket(encodedMessage, encodedMessage.length, droneAddress, dronePort);
            socket.send(udpPacket);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
    public void sendMAVLinkWaypoint(msg_mission_item waypoint) {
        try {
            MAVLinkPacket packet = waypoint.pack();
            byte[] encodedMessage = packet.encodePacket();
            DatagramPacket udpPacket = new DatagramPacket(encodedMessage, encodedMessage.length, droneAddress, dronePort);
            socket.send(udpPacket);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // Example functions for specific MAVLink commands
    public void armDrone() {
        sendMAVLinkCommand(MAV_CMD.MAV_CMD_COMPONENT_ARM_DISARM, 1);
    }

    public void disarmDrone() {
        sendMAVLinkCommand(MAV_CMD.MAV_CMD_COMPONENT_ARM_DISARM, 0);
    }

    public void takeOff() {
        sendMAVLinkCommand(MAV_CMD.MAV_CMD_NAV_TAKEOFF, 10); // 10m altitude
    }

    public void returnToLaunch() {
        sendMAVLinkCommand(MAV_CMD.MAV_CMD_NAV_RETURN_TO_LAUNCH, 0);
    }
}
