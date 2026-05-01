$ImageName = "finally"
$ContainerName = "finally-app"

# Change to project root
Set-Location "$PSScriptRoot\.."

# Check for .env file
if (!(Test-Path .env)) {
    Write-Error "Error: .env file not found. Please create one from .env.example."
    exit 1
}

# Build if image doesn't exist or if -Build flag is passed
$ImageExists = docker images -q $ImageName
if (!$ImageExists -or ($args -contains "--build")) {
    Write-Host "Building Docker image $ImageName..."
    docker build -t $ImageName .
}

# Stop existing container if running
$ContainerExists = docker ps -aq -f name=$ContainerName
if ($ContainerExists) {
    Write-Host "Stopping existing container..."
    docker rm -f $ContainerName
}

# Run the container
Write-Host "Starting FinAlly at http://localhost:8000"
docker run -d `
    --name $ContainerName `
    -p 8000:8000 `
    -v "$(Get-Item .)\db:/app/data" `
    --env-file .env `
    $ImageName

Write-Host "Container started. View at http://localhost:8000"
Write-Host "To view logs: docker logs -f $ContainerName"
Write-Host "To stop: .\scripts\stop_windows.ps1"
