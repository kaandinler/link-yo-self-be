#!/usr/bin/env bash
# LinkYoSelf: yayindan sonra duman testi. HICBIR SEY YAZMIYOR: hesap
# acmiyor, giris yapmiyor, tiklama saymiyor. Uretim verisini kirletmemesi
# ve hiz sinirini yakmamasi icin bilerek salt okuma.
#
#   bash deploy/smoke.sh                 # .env'den DOMAIN ve SMOKE_USERNAME
#   DOMAIN=ornek.com bash deploy/smoke.sh
#
# deploy/deploy.sh saglik kontrolunden sonra bunu calistiriyor; dusarse
# onceki surume donuluyor.
#
# Ayarlar (ortam degiskeni ya da .env):
#   DOMAIN          zorunlu
#   SMOKE_USERNAME  en az bir gorunur linki olan GERCEK bir profil. Verilirse
#                   web'in sunucu tarafinin API'ye ulastigi da dogrulaniyor
#                   (profil sayfasi API'den okunuyor). Verilmezse o kontrol
#                   atlanir ve uyari yazilir. Not: sitenin profil sayfasi her
#                   yayinda bir goruntulenme sayar.
#   SMOKE_API_BASE / SMOKE_SITE_BASE   test icin; varsayilan https://api.DOMAIN, https://DOMAIN

set -uo pipefail

BETIK_DIZINI="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ENV_DOSYASI="${ENV_DOSYASI:-$BETIK_DIZINI/../.env}"

env_oku() {
    [ -f "$ENV_DOSYASI" ] || return 0
    grep -E "^$1=" "$ENV_DOSYASI" | tail -1 | cut -d= -f2- | tr -d '"'"'"' '
}

DOMAIN="${DOMAIN:-$(env_oku DOMAIN)}"
SMOKE_USERNAME="${SMOKE_USERNAME:-$(env_oku SMOKE_USERNAME)}"
[ -n "$DOMAIN" ] || { echo "HATA: DOMAIN yok" >&2; exit 2; }
API="${SMOKE_API_BASE:-https://api.$DOMAIN}"
SITE="${SMOKE_SITE_BASE:-https://$DOMAIN}"

hata=0
gecti() { printf '  ok    %s\n' "$*"; }
dustu() { printf '  HATA  %s\n' "$*" >&2; hata=1; }

# kontrol <etiket> <kod> <kabul-edilen-kodlar-regex>
kontrol() {
    if [[ "$2" =~ ^($3)$ ]]; then gecti "$1 $2"; else dustu "$1: $2 (beklenen: $3)"; fi
}

# durum <url> -> HTTP kodu (yonlendirme izlenmez); baglanti yoksa 000
durum() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }

echo "duman testi: $SITE , $API"

# 1. API ayakta mi
kontrol "API kok" "$(durum "$API/")" 200

# 2. API veritabanina ulasiyor mu. "/" veritabanina dokunmuyor; bu uc
#    sayim yapiyor.
govde=$(curl -s --max-time 15 "$API/api/v1/p/sitemap/count")
if printf '%s' "$govde" | grep -q '"status" *: *"success"'; then
    gecti "API -> veritabani (sitemap/count)"
else
    dustu "API -> veritabani: beklenmeyen yanit: ${govde:0:200}"
fi

# 3. Site ayakta mi. "/" dil sayfasina yonleniyor; 3xx da ayakta demek.
kontrol "site kok" "$(durum "$SITE/")" "2[0-9][0-9]|3[0-9][0-9]"

# 4. robots.txt (Next'in kendi urettigi bir yanit, statik dosya degil)
kontrol "robots.txt" "$(durum "$SITE/robots.txt")" 200

# 5. Profil: API ve web -> API yolu
if [ -n "$SMOKE_USERNAME" ]; then
    kontrol "API profil /$SMOKE_USERNAME" "$(durum "$API/api/v1/p/$SMOKE_USERNAME?count_view=false")" 200

    # 404 burada web'in API'ye ulasamadigini ya da profilin gercekten
    # olmadigini gosterir; ikisi de yayini durdurmayi hak ediyor.
    kontrol "site profil /en/$SMOKE_USERNAME (web -> API)" "$(durum "$SITE/en/$SMOKE_USERNAME")" 200
else
    echo "  UYARI SMOKE_USERNAME yok: web -> API yolu dogrulanmadi" >&2
fi

# 6. Uretim davranisi: https zorunlu ve HSTS var. Yalnizca gercek alan
#    adinda anlamli; test tabanlarinda (SMOKE_*_BASE) atlaniyor.
if [ -z "${SMOKE_SITE_BASE:-}" ]; then
    kontrol "http -> https yonlendirmesi" "$(durum "http://$DOMAIN/")" "301|302|307|308"

    if curl -sI --max-time 15 "$SITE/" | grep -qi '^strict-transport-security:'; then
        gecti "HSTS basligi var"
    else
        dustu "HSTS basligi yok (Caddyfile uygulanmamis olabilir)"
    fi
fi

if [ "$hata" -ne 0 ]; then
    echo "duman testi DUSTU" >&2
    exit 1
fi
echo "duman testi gecti"
