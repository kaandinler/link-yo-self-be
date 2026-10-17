# syntax=docker/dockerfile:1

# LinkYoSelf API imaji.
#
#   docker build -t linkyoself-api .
#   docker run --env-file .env -p 8000:8000 linkyoself-api
#
# Migration'lar imajin ayaga kalkisinda CALISMIYOR; ayri bir adim:
#
#   docker run --env-file .env linkyoself-api alembic upgrade head
#
# NEDEN AYRI: baslangica konsaydi her kopya (WEB_CONCURRENCY>1 ya da
# birden fazla konteyner) ayni anda migration denerdi. docker-compose.yml
# bunu tek seferlik "migrate" servisiyle yapiyor; api o bitmeden kalkmiyor.

# Surum CI ile ayni (.github/workflows/tests.yml): testlerin gectigi
# yorumlayici uretimde kosan yorumlayici olsun.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Bagimliliklar kaynaktan ONCE: kod degistiginde bu katman onbellekten
# geliyor, pip yeniden calismiyor. Butun paketlerin (asyncpg, bcrypt,
# uvloop...) manylinux wheel'i var; derleyici gerekmiyor.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Root olarak kosmasin. Uygulamanin yazdigi tek yer yerel avatar deposu
# (STORAGE_BACKEND=local); /app'in geri kalani salt okunur kaliyor.
# docker-compose bu dizine bir birim bagliyor; birim ilk olusturuldugunda
# Docker icerigi ve SAHIBINI imajdaki dizinden kopyaliyor, yani buradaki
# chown birime de geciyor.
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /app/media && chown app /app/media
ENV MEDIA_ROOT=/app/media
USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-m", "scripts.healthcheck"]

# Isci sayisi WEB_CONCURRENCY'den (uvicorn kendisi okuyor; hiz siniri
# raporu da ayni degiskene bakiyor, bkz. core/rate_limit/limiter.py).
# 1'den buyukse REDIS_URL verilmeli, yoksa sinirlar isci basina sayilir.
#
# Ters vekil arkasinda: FORWARDED_ALLOW_IPS vekilin adresine ayarlanmali
# (uvicorn bunu da kendisi okuyor). Ayarlanmazsa X-Forwarded-Proto
# okunmuyor ve ENVIRONMENT=production'daki HTTPS yonlendirmesi her
# istegi -- zaten https ile gelmis olsa bile -- yeniden yonlendiriyor.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
