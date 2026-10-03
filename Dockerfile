FROM python:3.11-slim

# LightGBM needs the OpenMP runtime, which the slim image lacks
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

# only what serving needs: no training code, no raw data
COPY app.py features.py plan.py similar.py ./
COPY model.txt runs_model.txt wicket_model.txt meta.json zones.json profiles.npz ./
COPY static ./static

RUN useradd -m -u 1000 app
USER app
ENV PYTHONUNBUFFERED=1

# Cloud Run sets PORT (8080); other hosts can set their own
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
