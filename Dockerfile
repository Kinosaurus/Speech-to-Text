# Build natively on the Pi (ARM64) or laptop (AMD64) from the same source.
FROM python:3.12-slim-bookworm AS client
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential portaudio19-dev libsndfile1 ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-client.txt ./
RUN python -m pip install --no-cache-dir -r requirements-client.txt \
    && python -m pip install --no-cache-dir --no-deps whisper-live==0.10.0
COPY run_client.py run_server.py checkpoint_matcher.py alignment_matcher.py \
    checkpoint_demo.py audio_runtime.py asr_runtime.py prepare_models.py ./
COPY examples ./examples
COPY tests ./tests
RUN python -c "from whisper_live.client import TranscriptionClient; import alignment_matcher"
CMD ["python", "run_client.py", "--help"]

FROM client AS cpu
ENV CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
COPY requirements-cpu.txt requirements-asr.txt ./
RUN python -m pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r requirements-cpu.txt
RUN python -c "from whisper_live.backend.faster_whisper_backend import ServeClientFasterWhisper" \
    && python run_server.py --device cpu --check_device
EXPOSE 9090
CMD ["python", "run_server.py", "--device", "cpu", "--omp_num_threads", "2"]
