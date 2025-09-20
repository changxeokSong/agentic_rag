Param(
  [switch]$Rebuild
)

if ($Rebuild) {
  docker compose build --no-cache
}

docker compose up -d --remove-orphans

Write-Host "Containers are starting..."
Write-Host "Frontend: http://localhost:8501"
Write-Host "Postgres: localhost:5432 (user=synergy)"


