ARG ROS_DISTRO=humble
ARG OS=jammy
ARG FROM_IMAGE=astazero/atos_docker_env:latest  # Ensure this image exists

FROM ${FROM_IMAGE} AS application

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# Define application directory as an environment variable
ENV APP_DIR=/home/app/az-drone-safety-platform

# Set up workspace
WORKDIR /root/atos_ws/src

# Copy the new application into the container
COPY . ${APP_DIR}

# Ensure the directory exists before creating the symbolic link
RUN ln -s ${APP_DIR} /root/atos_ws/src/communication_software

# Build the application
WORKDIR /home/app/az-drone-safety-platform
RUN source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source /root/atos_ws/install/setup.sh && \
    colcon build # && \
    source ${APP_DIR}/install/local_setup.bash



# Source the built environment
# RUN echo "source /root/atos_ws/install/local_setup.bash" >> ~/.bashrc

# Default command: open a bash shell
# CMD ["/bin/bash"]
