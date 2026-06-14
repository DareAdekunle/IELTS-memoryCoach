FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies first
# Docker caches this layer so it only reruns when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose the Streamlit port
EXPOSE 8501

# Create a startup script that:
# 1. Initialises the database if it does not exist yet
# 2. Starts the Streamlit app
CMD ["sh", "-c", "python app/db/init_db.py && streamlit run app/main.py --server.address=0.0.0.0 --server.port=8501"]