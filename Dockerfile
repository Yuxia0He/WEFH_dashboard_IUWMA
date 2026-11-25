FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py content.json data.json evidence.json ssp_baseline.json ssp_policy_ensemble.json ./
COPY .streamlit/config.toml .streamlit/config.toml
COPY assets ./assets

EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
