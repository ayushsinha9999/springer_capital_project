# Use the official lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install the required dependencies 
RUN pip install pandas numpy

# Copy the Python script into the container
COPY data_pipeline.py .

# Copy the data folder into the container
COPY data/ ./data/

# Command to run the application
CMD ["python", "data_pipeline.py"]