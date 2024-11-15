# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files to the container
COPY . /app

# Install system dependencies for MeloTTS and Python dependencies in one step
RUN apt-get update && \
    apt-get install -y build-essential libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Download necessary linguistic resources and model files
RUN python -m unidic download && \
    python melo/init_downloads.py

# Expose the application port
EXPOSE 8888

# Run the application
CMD ["python", "./melo/app.py", "--host", "0.0.0.0", "--port", "8888"]
