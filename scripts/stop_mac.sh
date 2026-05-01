#!/bin/bash
CONTAINER_NAME="finally-app"

if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping and removing container $CONTAINER_NAME..."
    docker rm -f $CONTAINER_NAME
    echo "Done."
else
    echo "Container $CONTAINER_NAME is not running."
fi
