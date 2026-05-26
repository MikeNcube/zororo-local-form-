FROM python:3.11-slim

WORKDIR /app

# Copy JUST the requirements file straight into the root of the server
COPY ["requirements.txt", "./"]
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else straight into the root
COPY [".", "./"]

# Start the server directly from the root with Railway's dynamic port
CMD uvicorn main:app --host 0.0.0.0 --port $PORT