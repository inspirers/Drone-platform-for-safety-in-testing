FROM python:3.13-slim

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
RUN pip install lap

COPY image_stitching.py main.py
COPY annotator.py . 
COPY coordinateMapping.py .

CMD ["python", "main.py"]