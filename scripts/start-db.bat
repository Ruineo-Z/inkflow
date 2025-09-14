@echo off
echo Starting PostgreSQL with Docker Compose...
docker-compose up -d postgres

echo Waiting for PostgreSQL to be ready...
timeout /t 10 /nobreak > nul

echo PostgreSQL is ready!
echo Connection: postgresql://inkflow:inkflow123@localhost:5432/inkflow
echo.
echo You can now run your FastAPI application.
pause