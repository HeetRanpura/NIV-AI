FROM python:3.12-slim
WORKDIR /app

# Install system dependencies for Tesseract OCR and ZBar
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# CHANGED: Look at main.py in the current folder, not a subfolder
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]