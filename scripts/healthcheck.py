"""Konteyner saglik kontrolu (Dockerfile'daki HEALTHCHECK).

Surecin HTTP'ye cevap verip vermedigine bakar: 5xx disinda HERHANGI bir
yanit "ayakta" sayiliyor.

NEDEN 200 BEKLENMIYOR: ENVIRONMENT=production iken iki ara katman
devrede (bkz. main.create_app). TrustedHostMiddleware, ALLOWED_HOSTS'ta
olmayan Host basligina 400 donuyor; HTTPSRedirectMiddleware ise duz
HTTP istegini 307 ile https'e yonlendiriyor. Konteynerin icinden
127.0.0.1'e giden bir istek ikisine de takiliyor. 200 beklense uretimde
konteyner hep "unhealthy" gorunurdu -- ama 400 ve 307'yi uygulamanin
kendisi uretiyor, yani surec ayakta ve istek isliyor.

Yonlendirme bilerek izlenmiyor (http.client izlemez): izlenseydi
konteynerin icinde olmayan bir https adresine gidilirdi.

Veritabanina dokunmuyor. Bu bir canlilik kontrolu; veritabani kendi
saglik kontrolunu docker-compose'da tasiyor.
"""

import http.client
import os
import sys


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    try:
        baglanti = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        baglanti.request("GET", "/")
        durum = baglanti.getresponse().status
    except OSError as hata:
        print(f"saglik kontrolu: baglanilamadi: {hata}", file=sys.stderr)
        return 1

    if durum >= 500:
        print(f"saglik kontrolu: HTTP {durum}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
