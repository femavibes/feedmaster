# Use a lightweight Python base image
# python:3.10-slim-buster is a good choice for production as it's small
FROM python:3.10-slim-buster

# Set environment variables for Python to optimize performance and logging
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disk
# PYTHONUNBUFFERED: Ensures Python output is unbuffered, useful for Docker logs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container. All subsequent commands will run from here.
WORKDIR /app

# Create a non-root user for security best practices (optional but recommended for production)
# This prevents the application from running with root privileges inside the container
RUN adduser --system --group appuser
USER appuser

# Copy the requirements file into the container
# Copying it first allows Docker to cache this layer. If only your code changes,
# dependencies won't be reinstalled, speeding up builds.
# Ensure this path is correct relative to your Dockerfile.
# If your requirements.txt is in 'backend/', the path 'backend/requirements.txt' is correct.
COPY backend/requirements.txt .

# Install Python dependencies
# --no-cache-dir: Prevents pip from storing cached wheels, reducing image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
# Make sure your 'backend' directory is at the root of your build context (where Dockerfile is)
# This copies everything from your host's current directory (where Dockerfile is) to /app in container
COPY . .

# Set PYTHONPATH to include your application's root directory,
# especially if your modules are in a 'backend' folder
# This helps Python find your modules like 'backend.main'
ENV PYTHONPATH=/app

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the FastAPI application using Uvicorn
# The --host 0.0.0.0 makes the server accessible from outside the container
# Use the exec form (list of strings) for better signal handling (e.g., graceful shutdown)
# Ensure 'backend.main:app' is the correct module and app object.
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]