#!/bin/bash
set -e

# Change to project root
cd "$(dirname "$0")/.."

IMAGE_NAME="finally"
CONTAINER_NAME="finally-app"

# Check for .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create one from .env.example."
    exit 1
fi

# Build if image doesn't exist or if --build is passed
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]] || [[ "$1" == "--build" ]]; then
    echo "Building Docker image $IMAGE_NAME..."
    docker build -t $IMAGE_NAME .
fi

# Stop existing container if running
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping existing container..."
    docker rm -f $CONTAINER_NAME
fi

# Run the container
echo "Starting FinAlly at http://localhost:8000"
docker run -d \
    --name $CONTAINER_NAME \
    -p 8000:8000 \
    -v "$(pwd)/db:/app/data" \
    --env-file .env \
    $IMAGE_NAME

echo "Container started. View at http://localhost:8000"
echo "To view logs: docker logs -f $CONTAINER_NAME"
echo "To stop: ./scripts/stop_mac.sh"
