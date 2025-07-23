# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# 1. Install system dependencies and add Google's official repository
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    --no-install-recommends \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# 2. Install Google Chrome Stable. The chromedriver is included automatically.
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends

# 3. Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the application's code
COPY . .

# 5. Expose the port for the web server
EXPOSE 10000

# 6. Command to run the application
CMD ["python", "telegram_bot.py"]
