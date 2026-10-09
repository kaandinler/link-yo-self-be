"""Kullanicinin yukledigi dosyalarin deposu (bugun yalnizca avatarlar).

Iki uygulama var, ayar STORAGE_BACKEND ile seciliyor:

- YerelDepo: dosyalar diske yaziliyor, uygulama /media altindan sunuyor.
- S3Depo: S3 uyumlu bir kova (AWS S3, Cloudflare R2, MinIO).

Ikisi ayni arayuzu tasiyor; uclar hangisinin kullanildigini bilmiyor.
"""

from core.storage.base import Depo, avatar_anahtari, avatar_anahtari_mi
from core.storage.factory import depo_olustur

__all__ = ["Depo", "avatar_anahtari", "avatar_anahtari_mi", "depo_olustur"]
