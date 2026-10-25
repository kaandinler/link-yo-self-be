#!/usr/bin/env bash
# LinkYoSelf: sunucuda bir surumu yayina alir; basarisizsa onceki surume doner.
#
# Deploy workflow'u (.github/workflows/deploy.yml) bu betigi SSH uzerinden
# stdin'den calistiriyor:
#
#   ssh deploy@sunucu 'bash -s -- <be-ref> <fe-ref>' < deploy/deploy.sh
#
# Elle de calisir (sunucuda, deploy kullanicisi olarak):
#
#   bash /srv/linkyoself/link-yo-self-be/deploy/deploy.sh origin/main origin/main
#
# NEDEN STDIN'DEN: betik depoyu checkout ediyor. Diskteki kopyasindan
# calissaydi, checkout calisan betigin altindaki dosyayi degistirirdi
# (bash betigi satir satir okuyor) ve sonuc tanimsiz olurdu.
#
# ADIMLAR
#   1. Yedek (yigin calisiyorsa): geri donus veritabanini da kurtarabilsin
#   2. Iki depoyu istenen surume al; onceki surumleri kaydet
#   3. Imajlari DERLE (calisan konteynerlere dokunmadan)
#   4. up -d: migrate -> api -> web -> caddy
#   5. Saglik kontrolu: https://api.DOMAIN/ ve https://DOMAIN/
#   6. 3-5'ten biri duserse: onceki surumlere don, yeniden kaldir, 1 ile cik
#
# BILINEN SINIR: geri donus migration'lari GERI ALMIYOR. Yeni surumun
# migration'i calistiysa eski kod yeni semayla kosar. Migration'larin
# geriye uyumlu yazilmasi (once sutun ekle, sonra kullan, sonra kaldir)
# bunu guvenli kiliyor; uyumsuz bir migration'da 1. adimdaki yedekten
# geri yukleyin (deploy/restore.md).

set -euo pipefail

# BUTUN GOVDE BIR FONKSIYONDA ve en sonda tek satirda cagriliyor.
#
# NEDEN: betik `ssh ... 'bash -s'` ile pipe'tan okunuyor ve bash pipe'tan
# okurken komutlari tek tek, okudukca calistiriyor. stdin'i okuyan herhangi
# bir alt surec (docker compose exec, ssh ...) betigin GERI KALANINI yutar
# ve bash sessizce biter -- is yesil, yayin yapilmamis. Fonksiyon sayesinde
# bash once butun govdeyi okuyor; `exec </dev/null` da alt sureclerin
# stdin'ini kapatiyor (bagimsiz incelemede bulundu).
main() {
    exec < /dev/null

    BE_REF="${1:-origin/main}"
    FE_REF="${2:-origin/main}"
    APP_DIR="${APP_DIR:-/srv/linkyoself}"
    BE="$APP_DIR/link-yo-self-be"
    FE="$APP_DIR/link-yo-self-fe"
    SAGLIK_DENEME="${SAGLIK_DENEME:-36}" # x5 sn = 3 dk (ilk TLS sertifikasi dahil)

    adim() { printf '\n==> %s\n' "$*"; }
    dur() { printf '\nHATA: %s\n' "$*" >&2; exit 1; }

    compose() {
        docker compose --project-directory "$BE" \
            -f "$BE/docker-compose.yml" -f "$BE/deploy/docker-compose.prod.yml" "$@"
    }

    [ -f "$BE/.env" ] || dur "$BE/.env yok (sablon: deploy/.env.prod.example)"
    # Satir sonundaki "# yorum" ve tirnaklar ayiklaniyor (DOMAIN=x # not -> x).
    DOMAIN="$(grep -E '^DOMAIN=' "$BE/.env" | tail -1 | cut -d= -f2- | sed 's/[[:space:]]#.*//' | tr -d '"'"'"' ')"
    [ -n "$DOMAIN" ] || dur ".env'de DOMAIN bos"

    # --- 1. Yedek --------------------------------------------------------------
    adim "Yedek"
    # Once yapilandirma: `compose ps` bozuk bir .env'de hata verir ve asagidaki
    # kontrol bunu "db calismiyor" sanip YEDEKSIZ devam ederdi.
    compose config -q || dur "compose yapilandirmasi gecersiz (.env?)"
    if [ -n "$(compose ps -q db)" ]; then
        bash "$BE/deploy/backup.sh"
    else
        echo "    db calismiyor (ilk kurulum?); atlandi"
    fi

    # --- 2. Surumler -----------------------------------------------------------
    adim "Surumler"
    ONCEKI_BE="$(git -C "$BE" rev-parse HEAD)"
    ONCEKI_FE="$(git -C "$FE" rev-parse HEAD)"

    surume_al() {
        # $1 depo dizini, $2 ref. Yerel degisiklik varsa durur: sunucuda elle
        # duzenlenmis bir dosyanin sessizce ezilmesi istenmez.
        if [ -n "$(git -C "$1" status --porcelain --untracked-files=no)" ]; then
            echo "    $1 icinde yerel degisiklik var; once inceleyin (git -C $1 status)" >&2
            return 1
        fi
        git -C "$1" fetch --quiet --prune origin && git -C "$1" checkout --quiet --detach "$2"
    }

    checkout_geri_al() {
        git -C "$BE" checkout --quiet --detach "$ONCEKI_BE"
        git -C "$FE" checkout --quiet --detach "$ONCEKI_FE"
    }

    # Biri duserse IKISI de onceki surume: yoksa BE yeni commit'te, calisan
    # konteynerler eski derlemede kalir ve bir sonraki yayin geri donus icin
    # yanlis "onceki" surumu kaydederdi.
    if ! { surume_al "$BE" "$BE_REF" && surume_al "$FE" "$FE_REF"; }; then
        checkout_geri_al
        dur "surume alinamadi (ref: be=$BE_REF fe=$FE_REF); calisan surume dokunulmadi"
    fi
    YENI_BE="$(git -C "$BE" rev-parse HEAD)"
    YENI_FE="$(git -C "$FE" rev-parse HEAD)"
    echo "    be: ${ONCEKI_BE:0:7} -> ${YENI_BE:0:7}"
    echo "    fe: ${ONCEKI_FE:0:7} -> ${YENI_FE:0:7}"

    saglikli_mi() {
        local i
        for i in $(seq 1 "$SAGLIK_DENEME"); do
            # Yonlendirme izlenmiyor: "/" dil sayfasina yonleniyor ve 3xx de
            # sitenin ayakta oldugunu gosteriyor. -f 4xx/5xx'te dusuruyor.
            if curl -fsS -o /dev/null --max-time 10 "https://api.$DOMAIN/" \
                && curl -fsS -o /dev/null --max-time 10 "https://$DOMAIN/"; then
                echo "    saglikli (deneme $i)"
                return 0
            fi
            sleep 5
        done
        return 1
    }

    geri_don() {
        adim "GERI DONUS: be ${ONCEKI_BE:0:7}, fe ${ONCEKI_FE:0:7}"
        checkout_geri_al
        compose build && compose up -d --remove-orphans
        if saglikli_mi; then
            echo "    onceki surum ayakta"
        else
            echo "    ONCEKI SURUM DE SAGLIKSIZ -- elle mudahale gerekli (compose logs)" >&2
        fi
        exit 1
    }

    # --- 3. Derleme ------------------------------------------------------------
    # Calisan konteynerlere dokunmuyor: derleme duserse site eski surumle
    # ayakta kaliyor, yalnizca checkout geri aliniyor.
    adim "Derleme"
    if ! compose build; then
        checkout_geri_al
        dur "derleme basarisiz; calisan surume dokunulmadi"
    fi

    # --- 4. Yayin --------------------------------------------------------------
    adim "Yayin"
    compose up -d --remove-orphans || geri_don

    # --- 5. Saglik ---------------------------------------------------------------
    adim "Saglik kontrolu: https://api.$DOMAIN/ ve https://$DOMAIN/"
    saglikli_mi || { compose ps; compose logs --tail 50 api web caddy; geri_don; }

    docker image prune -f > /dev/null
    adim "Yayinda: be ${YENI_BE:0:7}, fe ${YENI_FE:0:7}"
}

main "$@"; exit
