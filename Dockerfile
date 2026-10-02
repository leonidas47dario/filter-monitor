# Filter Monitor — one image for every command (check, roi, collect, staged).
FROM ubuntu:24.04

# Python, ffmpeg (pulls the camera stream) and tzdata (local time in clip names and the manifest).
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg tzdata ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
# Containers have no screen, so use the headless OpenCV build.
RUN sed 's/^opencv-python>/opencv-python-headless>/' requirements.txt > /tmp/req.txt \
 && pip install --no-cache-dir -r /tmp/req.txt

COPY filter_monitor/ filter_monitor/

ENTRYPOINT ["python", "-m", "filter_monitor"]
CMD ["--help"]
