package com.dji.sdk.sample;

import static dji.midware.data.manager.P3.ServiceManager.getContext;

import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;


import java.util.ArrayList;
import java.util.List;

import dji.common.error.DJIError;
import dji.common.flightcontroller.FlightControllerState;
import dji.common.flightcontroller.GPSSignalLevel;
import dji.common.mission.waypoint.Waypoint;
import dji.common.mission.waypoint.WaypointAction;
import dji.common.mission.waypoint.WaypointActionType;
import dji.common.mission.waypoint.WaypointMission;
import dji.common.mission.waypoint.WaypointMissionDownloadEvent;
import dji.common.mission.waypoint.WaypointMissionExecutionEvent;
import dji.common.mission.waypoint.WaypointMissionFinishedAction;
import dji.common.mission.waypoint.WaypointMissionFlightPathMode;
import dji.common.mission.waypoint.WaypointMissionHeadingMode;
import dji.common.mission.waypoint.WaypointMissionUploadEvent;
import dji.common.battery.BatteryState;
import dji.sdk.flightcontroller.FlightController;
import dji.sdk.mission.waypoint.WaypointMissionOperator;
import dji.sdk.mission.waypoint.WaypointMissionOperatorListener;
import dji.sdk.products.Aircraft;
import dji.sdk.sdkmanager.DJISDKManager;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import com.MAVLink.common.msg_command_long;
import com.MAVLink.enums.MAV_CMD;
import com.MAVLink.MAVLinkPacket;
import com.MAVLink.common.msg_mission_item;


class FlightManager {
    private final float mSpeed = 6.0f; // Reasonable operatingspeed for the drone decided after testing
    private List<Waypoint> waypointList = new ArrayList<>(); //List for storing waypoint / -s
    private List<WaypointAction> primarywaypointActions = new ArrayList<>();
    public static WaypointMission.Builder waypointMissionBuilder;
    private WaypointMissionOperator waypointMissionOperator;
    private WaypointMissionFinishedAction mFinishedAction = WaypointMissionFinishedAction.CONTINUE_UNTIL_END;
    private WaypointMissionHeadingMode mHeadingMode = WaypointMissionHeadingMode.AUTO;
    private WaypointMissionFlightPathMode mFlightPathMode = WaypointMissionFlightPathMode.NORMAL;
    private FlightController controller;
    private BatteryState batteryState;
    private static FlightManager flightManager = null;
    private FlightControllerState state;
    private Aircraft aircraft;
    private CoordinatesActivity coordinatesActivity;
    public double input_lat;
    public double input_lng;
    public float input_alt;
    public int input_yaw;
    private WaypointMissionOperatorListener eventNotificationListener;


    private String getDroneMode() {
        SharedPreferences prefs = getContext().getSharedPreferences("AppSettings", Context.MODE_PRIVATE);
        return prefs.getString("droneMode", "DJI"); // Default to DJI mode
    }   
    
    private FlightManager(){
        this.aircraft = (Aircraft) DJISDKManager.getInstance().getProduct();
        aircraft.getFlightController().setStateCallback(new FlightControllerState.Callback() {
            @Override
            public void onUpdate(@NonNull FlightControllerState flightControllerState) {
                state = flightControllerState;
            }
        });
        aircraft.getBattery().setStateCallback(new BatteryState.Callback() {
            @Override
            public void onUpdate(BatteryState batteryState) {
                FlightManager.this.batteryState = batteryState;
            }
        });
        controller = aircraft.getFlightController();

        /**
         * See DJI Google Maps demo.
         */
        eventNotificationListener = new WaypointMissionOperatorListener() {
            @Override
            public void onDownloadUpdate(WaypointMissionDownloadEvent downloadEvent) {
            }
            @Override
            public void onUploadUpdate(WaypointMissionUploadEvent uploadEvent) {
            }
            @Override
            public void onExecutionUpdate(WaypointMissionExecutionEvent executionEvent) {
            }
            @Override
            public void onExecutionStart() {
            }
            @Override
            public void onExecutionFinish(@Nullable final DJIError error) {
            }
        };
    }

    /**
     * Returns the singleton instance of the FlightManager class. If the FlightManger is not
     * instantiated, it is.
     * @return The singleton instance of FlightManager
     */
    public static synchronized FlightManager getFlightManager(){
        if (flightManager == null){
            flightManager = new FlightManager();
        }
        return flightManager;
    }

    /**
     * @return The WaypointMissionOperator if the drone is connected, otherwise null
     */
    @Nullable
    public WaypointMissionOperator getWaypointMissionOperator() {
        if (waypointMissionOperator == null) {
            if (DJISDKManager.getInstance().getMissionControl() != null){
                waypointMissionOperator = DJISDKManager.getInstance().getMissionControl().getWaypointMissionOperator();
            }
        }
        return waypointMissionOperator;
    }

    public FlightController getController() {
        return controller;
    }

    public FlightControllerState getState() {
        return state;
    }

    public Aircraft getAircraft() {
        return aircraft;
    }

    public CoordinatesActivity getCoordinatesActivity() {
        return coordinatesActivity;
    }

    /**
     * This function starts the process of setting up the waypoint mission and is called when
     * the user presses the Arm button.
     * Firstly we check the batterystate to ensure the drones battery is above 20% as the the
     * application just crashes otherwise.
     * Secondly checking that gps connection is ensured
     * To ensure a correct mission, possible leftovers of previous missions is deleted.
     * It fetches the coordinates of the drone on the ground and creating the first waypoint 10 m above.
     * Thereafter we fetch the test origin coordinates loaded from either the user manually or from ATOS.
     * The waypoints are then put in a list by order of execution,
     * so our primary waypoint is added lastly.
     * Lastly we call configWaypointMission() to further specify the behavior of the waypointMission and
     * uploadWaypointMission() to send the finished product to the drone
     *
     * @input_lat Latitude of test origin set either directly by user or ATOS
     * @input_lng Longitude of test origin set either directly by user or ATOS
     * @input_alt Altitude at test origin required to capture the entirety of the test area
     */
    public void onArm() {
        // Retrieve selected mode (DJI or MAVLink)
        String droneMode = getDroneMode();
        Log.d("FlightManager", "Selected Mode: " + droneMode);
    
        if (droneMode.equals("MAVLink")) {
            startMAVLinkMission();
            return; // Prevents running DJI-specific code
        }
    
        // **DJI Mode Logic (UNCHANGED)**
        int batteryPercent = batteryState.getChargeRemainingInPercent();
        if (batteryPercent <= 20) {
            Toast.makeText(getContext(), "Battery too low to start mission, needs above 20%. Is: " + batteryPercent + "%", Toast.LENGTH_LONG).show();
            return;
        }
    
        GPSSignalLevel gpsSignalLevel = state.getGPSSignalLevel();
        if ((Integer) gpsSignalLevel.value() <= 1 || gpsSignalLevel == GPSSignalLevel.NONE) {
            Toast.makeText(getContext(), "GPS not good enough, try again!", Toast.LENGTH_SHORT).show();
            return;
        }
    
        waypointList.clear();
        primarywaypointActions.clear();
    
        double raw_lat = state.getAircraftLocation().getLatitude();
        double raw_lng = state.getAircraftLocation().getLongitude();
        float lat = (float) raw_lat;
        float lng = (float) raw_lng;
        float alt = 10;
    
        Waypoint mWaypoint = new Waypoint(input_lat, input_lng, input_alt);
    
        if (waypointMissionBuilder == null) {
            waypointMissionBuilder = new WaypointMission.Builder();
        }
    
        waypointList.add(new Waypoint(lat, lng, alt));
        waypointMissionBuilder.waypointList(waypointList).waypointCount(waypointList.size());
    
        waypointList.add(mWaypoint);
        waypointMissionBuilder.waypointList(waypointList).waypointCount(waypointList.size());
    
        configWayPointMission();
        uploadWayPointMission();

    // SPECIFIC MAVLINK MISSION STARTER    
    }
    private void startMAVLinkMission() {
        Log.d("FlightManager", "Starting MAVLink mission");
    
        MAVLinkStarter mavLinkStarter = new MAVLinkStarter("192.168.1.2"); // Replace with actual drone IP

        // ARM Drone
        mavLinkStarter.sendMAVLinkCommand(MAV_CMD.MAV_CMD_COMPONENT_ARM_DISARM, 1);
        Log.d("FlightManager", "MAVLink - Drone Armed");

        // Takeoff 
        mavLinkStarter.sendMAVLinkCommand(MAV_CMD.MAV_CMD_NAV_TAKEOFF, 10);
        Log.d("FlightManager", "MAVLink - Takeoff Command Sent");
    
        Toast.makeText(getContext(), "MAVLink mission started!", Toast.LENGTH_SHORT).show();
    }
    
    

    /**
     * ConfigWayPointMission() extends the onArm function and builds the characteristics of the waypoint mission.
     * We set finishedAction and headingMode to what was defined in onArm()
     * We continue to define alla actions for our waypoint (test origin) in primaryWaypointActions
     * The list is connected to our main waypoint on index 1
     * After all configurations are complete the mission is ready to be uploaded to the drone
     *
     * @mFinishedAction Value of what behavior we want the drone to have after completing the final waypoint action
     * @mHeadingMode Value of what behavior we want when the drone flies between waypoints
     * @mSpeed The operating speed of the drone between the waypoints. In this case, auto and max is
     * set to the same for simplicity
     * @mFlightPathMode Defines how to fly between waypoints, either in a curve or straight(NORMAL).
     * In this case, NORMAL is used
     */
    private void configWayPointMission(){
        if (waypointMissionBuilder == null){
            waypointMissionBuilder = new WaypointMission.Builder().finishedAction(mFinishedAction)
                    .headingMode(mHeadingMode)
                    .autoFlightSpeed(mSpeed)
                    .maxFlightSpeed(mSpeed)
                    .flightPathMode(mFlightPathMode);
        }else
        {
            waypointMissionBuilder.finishedAction(mFinishedAction)
                    .headingMode(mHeadingMode)
                    .autoFlightSpeed(mSpeed)
                    .maxFlightSpeed(mSpeed)
                    .flightPathMode(mFlightPathMode);
        }

        // Setting action on primary waypoint to point gimbal straight down and to
        // rotate if input has been given to cover ground more efficiently
        primarywaypointActions.add(new WaypointAction(WaypointActionType.GIMBAL_PITCH, -90));
        primarywaypointActions.add(new WaypointAction(WaypointActionType.ROTATE_AIRCRAFT, input_yaw));

        if (waypointMissionBuilder.getWaypointList().size() >= 2) {
            waypointMissionBuilder.getWaypointList().get(1).waypointActions = primarywaypointActions;
        } else{
            Toast.makeText(getContext(), "Wrong amount of missions loaded", Toast.LENGTH_SHORT).show();
        }

        DJIError error = getWaypointMissionOperator().loadMission(waypointMissionBuilder.build());
        if (error != null) {
            Toast.makeText(getContext(), "loadWaypoint failed in stage config " + error.getDescription(), Toast.LENGTH_SHORT).show();
        }
    }

    /**
     * Sends mission details to the drone after everything has been configured
     */
    private void uploadWayPointMission(){
        getWaypointMissionOperator().uploadMission(error -> {
            if (error == null) {
                Toast.makeText(getContext(), "Mission upload successfully!", Toast.LENGTH_SHORT).show();

            } else {
                Toast.makeText(getContext(), "Mission upload failed, error: " + error.getDescription() + " retrying...", Toast.LENGTH_SHORT).show();
                getWaypointMissionOperator().retryUploadMission(null);
            }
        });
    }

    /**
     * Starts the waypoint mission. If a mission is uploaded, the drone will ACTUALLY TAKE OFF when this
     * method is called.
     */
    public void startWaypointMission(){

            // Drone Mode
            String droneMode = getDroneMode();
            Log.d("FlightManager", "Selected Mode: " + droneMode);

            if (droneMode.equals("MAVLink")) {
                // Start MAVLink waypoint mission
                startMAVLinkWaypointMission();
            } else {
                // Start DJI waypoint mission
                getWaypointMissionOperator().startMission(error -> 
                    Toast.makeText(getContext(), "Mission Start: " + (error == null ? "Successfully" : error.getDescription()), Toast.LENGTH_SHORT).show()
                );
            }
        }

        private void startMAVLinkWaypointMission() {
            Log.d("FlightManager", "Starting MAVLink Waypoint Mission");
        
            MAVLinkStarter mavLinkStarter = new MAVLinkStarter("192.168.1.2"); // Replace with drone IP
        
            // Convert DJI waypoints to MAVLink waypoints
            for (Waypoint djiWaypoint : waypointList) {
                msg_mission_item mavWaypoint = new msg_mission_item();
                mavWaypoint.x = (float) djiWaypoint.coordinate.getLatitude();
                mavWaypoint.y = (float) djiWaypoint.coordinate.getLongitude();
                mavWaypoint.z = djiWaypoint.altitude;
                mavWaypoint.command = MAV_CMD.MAV_CMD_NAV_WAYPOINT;
                mavWaypoint.target_system = 1;
                mavWaypoint.target_component = 1;
                mavWaypoint.autocontinue = 1;
        
                // Send each MAVLink waypoint
                mavLinkStarter.sendMAVLinkWaypoint(mavWaypoint);
                try { Thread.sleep(500); } catch (InterruptedException e) { e.printStackTrace(); } // Small delay
            }
        
            // Start MAVLink Mission
            msg_command_long startMission = new msg_command_long();
            startMission.command = MAV_CMD.MAV_CMD_MISSION_START;
            startMission.target_system = 1;
            startMission.target_component = 1;
            mavLinkStarter.sendMAVLinkCommand(startMission);
        
            Log.d("FlightManager", "MAVLink Waypoint Mission Sent!");
        }

    /**
     * Function for terminating current waypoint mission.
     * This function is directly used when the Abort button is pressed
     * When called, the drone exits the waypoint mission and hovers in current position with manual controls activated
     */
    public void abortWaypointMission() {
        // Drone Mode
        String droneMode = getDroneMode();
        Log.d("FlightManager", "Selected Mode: " + droneMode);
    
        if (droneMode.equals("MAVLink")) {
            // Stop MAVLink waypoint mission
            abortMAVLinkMission();
        } else {
            // Stop DJI waypoint mission
            getWaypointMissionOperator().stopMission(error -> 
                Toast.makeText(getContext(), "Mission Stop: " + (error == null ? "Successfully" : error.getDescription()), Toast.LENGTH_SHORT).show()
            );
        }
    }
    
    private void abortMAVLinkMission() {
        Log.d("FlightManager", "Aborting MAVLink mission");
    
        MAVLinkStarter mavLinkStarter = new MAVLinkStarter("192.168.1.2");  // Replace with drone IP
    
        // Abort Mission
        msg_command_long stopMission = new msg_command_long();
        stopMission.command = MAV_CMD.MAV_CMD_DO_SET_MODE;
        stopMission.param1 = 6; // MAV_MODE_GUIDED_DISARMED (Stops mission)
        stopMission.target_system = 1;
        stopMission.target_component = 1;
        mavLinkStarter.sendMAVLinkCommand(stopMission);
    
        try { Thread.sleep(2000); } catch (InterruptedException e) { e.printStackTrace(); } // Wait 2 sec
    
        // Land the Drone
        msg_command_long landCommand = new msg_command_long();
        landCommand.command = MAV_CMD.MAV_CMD_NAV_LAND;
        landCommand.target_system = 1;
        landCommand.target_component = 1;
        mavLinkStarter.sendMAVLinkCommand(landCommand);
    
        try { Thread.sleep(5000); } catch (InterruptedException e) { e.printStackTrace(); } // Wait 5 sec
    
        // Disarm Drone
        msg_command_long disarmCommand = new msg_command_long();
        disarmCommand.command = MAV_CMD.MAV_CMD_COMPONENT_ARM_DISARM;
        disarmCommand.param1 = 0;  // Disarm
        disarmCommand.target_system = 1;
        disarmCommand.target_component = 1;
        mavLinkStarter.sendMAVLinkCommand(disarmCommand);
    
        Log.d("FlightManager", "MAVLink mission aborted, drone landing...");
        Toast.makeText(getContext(), "MAVLink mission aborted, landing drone.", Toast.LENGTH_SHORT).show();
    }
    

    /**
     * Function to use when everything is done and the test is completed.
     * Waypointmode is stopped and the drone returns to home to start position.
     */
    public void endWaypointMission(){
        abortWaypointMission();
        goingHome();
    }


    /**
     * Implements the DJI function startGoHome.
     * Is called when test is complete
     */
    public void goingHome() {
        // Get the current drone mode (DJI or MAVLink)
        String droneMode = getDroneMode();
        Log.d("FlightManager", "Going Home - Mode: " + droneMode);
    
        if (droneMode.equals("MAVLink")) {
            goHomeMAVLink(); // Use MAVLink Return-To-Launch command
        } else {
            controller.startGoHome(djiError -> {
                if (djiError == null) {
                    Toast.makeText(getContext(), "Returning to Home (DJI)...", Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(getContext(), djiError.getDescription(), Toast.LENGTH_SHORT).show();
                }
            });
        }
    }

    private void goHomeMAVLink() {
        Log.d("FlightManager", "Initiating MAVLink RTL");
    
        MAVLinkStarter mavLinkStarter = new MAVLinkStarter("192.168.1.2");  // Replace with actual IP
    
        // MAVLink Return to Home
        msg_command_long rtlCommand = new msg_command_long();
        rtlCommand.command = MAV_CMD.MAV_CMD_NAV_RETURN_TO_LAUNCH;
        rtlCommand.target_system = 1;
        rtlCommand.target_component = 1;
        mavLinkStarter.sendMAVLinkCommand(rtlCommand);
    
        Log.d("FlightManager", "MAVLink RTL command sent.");
        Toast.makeText(getContext(), "Returning to Launch (MAVLink)...", Toast.LENGTH_SHORT).show();
    }
    
    

    @Deprecated
    void setHomeLocationUsingAircraftCurrentLocation() {    
    // Get the current drone mode (DJI or MAVLink)
    String droneMode = getDroneMode();
    Log.d("FlightManager", "Setting Home Location - Mode: " + droneMode);

    if (droneMode.equals("MAVLink")) {
        setMAVLinkHomeLocation(); // MAVLink Home Location
    } else {
        // **DJI Set Home Location**
        controller.setHomeLocationUsingAircraftCurrentLocation(djiError -> {
            if (djiError == null) {
                Toast.makeText(getCoordinatesActivity(), "Home set (DJI) :)", Toast.LENGTH_SHORT).show();
            } else {
                Toast.makeText(getCoordinatesActivity(), djiError.getDescription(), Toast.LENGTH_SHORT).show();
            }
        });
    }
    }

    private void setMAVLinkHomeLocation() {
        Log.d("FlightManager", "Setting MAVLink Home Location...");
    
        MAVLinkStarter mavLinkStarter = new MAVLinkStarter("192.168.1.2");  // Replace with actual drone IP
    
        msg_command_long homeCommand = new msg_command_long();
        homeCommand.command = MAV_CMD.MAV_CMD_DO_SET_HOME;
        homeCommand.param1 = 1;  // 1 = Use current position as home
        homeCommand.target_system = 1;
        homeCommand.target_component = 1;
        mavLinkStarter.sendMAVLinkCommand(homeCommand);
    
        Log.d("FlightManager", "MAVLink Home Location Set.");
        Toast.makeText(getContext(), "Home location set (MAVLink)!", Toast.LENGTH_SHORT).show();
    }
    


    /**
     * See the DJI documentation for the Google Maps Demo app.
     */
    public void addListener() {
        if (getWaypointMissionOperator() != null) {
            getWaypointMissionOperator().addListener(eventNotificationListener);
        }
    }

    /**
     * See the DJI documentation for the Google Maps Demo app.
     */
    public void removeListener() {
        if (getWaypointMissionOperator() != null) {
            getWaypointMissionOperator().removeListener(eventNotificationListener);
        }
    }



}