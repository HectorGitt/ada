FROM python:3.11-slim AS build
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright
COPY src ./src
# Migrations ship with the image so `alembic upgrade head` can run as a
# Cloud Run Job release step (the ada-migrate job) before traffic shifts.
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
USER appuser
EXPOSE 8080
CMD ["uvicorn", "ada.main:app", "--host", "0.0.0.0", "--port", "8080"]
