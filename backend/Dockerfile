FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY tribev2/ /tribev2/
COPY backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY backend/scripts/apply_neuralset_mps.py scripts/apply_neuralset_mps.py
RUN python scripts/apply_neuralset_mps.py
COPY backend/scripts/prepare_assets.py backend/scripts/generate_roi_atlas.py scripts/
COPY scripts/generate_splayed_meshes.py /scripts/generate_splayed_meshes.py
COPY backend/app/ app/
COPY backend/static/ static/

RUN useradd --create-home --uid 10001 neurolens \
    && mkdir -p /data/uploads /data/results /data/cache /data/references /data/assets \
    && chown -R neurolens:neurolens /data
USER neurolens
ENV HF_HOME=/data/cache/huggingface
ENV MNE_DATA=/data/cache/mne

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--no-proxy-headers", "--port", "8000"]
