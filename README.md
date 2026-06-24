# Springer Capital - Referral Program Data Pipeline

## Overview
This repository contains a robust data pipeline built in Python (Pandas) to model a user referral program. It cleanses raw log data, performs complex timezone conversions, and implements strict business logic to evaluate valid and invalid referral rewards to prevent fraud. 

## Prerequisites
* Docker installed on your machine.
* Raw CSV data stored locally in a `data/` directory.

## Running the Application via Docker

**1. Build the Docker Image**
Open your terminal in the root directory of this project and run:
`docker build -t springer-data-pipeline .`

**2. Run the Container and Export the Report**
To ensure the `final_referral_report.csv` is exported to your local machine (outside the container), run the container with a volume mount:

**For Mac/Linux:**
`docker run -v $(pwd):/app/output springer-data-pipeline`

**For Windows (Command Prompt):**
`docker run -v "%cd%":/app/output springer-data-pipeline`

*Note: If using the volume mount, ensure the Python script output path is updated to save to the mapped `/app/output/` directory.*
