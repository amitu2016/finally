$ContainerName = "finally-app"

$ContainerExists = docker ps -aq -f name=$ContainerName
if ($ContainerExists) {
    Write-Host "Stopping and removing container $ContainerName..."
    docker rm -f $ContainerName
    Write-Host "Done."
} else {
    Write-Host "Container $ContainerName is not running."
}
