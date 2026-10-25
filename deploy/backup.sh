#!/usr/bin/env bash
# LinkYoSelf: veritabani ve avatar yedegi. Sunucuda, deploy kullanicisi
# olarak, cron'dan:
#
#   15 3 * * *  /srv/linkyoself/link-yo-self-be/deploy/backup.sh >> /srv/linkyoself/backups/backup.log 2>&1
#
# Her calisma iki dosya uretiyor:
#   db-<zaman>.dump      pg_dump ozel bicim (sikistirilmis, pg_restore ile)
#   media-<zaman>.tgz    yerel avatar deposu (STORAGE_BACKEND=local ise)
#
# Geri yukleme: deploy/restore.md.
#
# Ayarlar (ortam degiskeni):
#   BACKUP_DIR      varsayilan: /srv/linkyoself/backups
#   KEEP_DAYS       varsayilan: 7
#   RCLONE_REMOTE   bos (varsayilan): yalnizca yerel kopya.
#                   Doluysa (ornegin "r2:linkyoself-yedek") her yedek
#                   rclone ile oraya da kopyalaniyor. rclone kurulu ve
#                   yapilandirilmis olmali (bkz. deploy/restore.md).

set -euo pipefail

BETIK_DIZINI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPO="$(dirname "$BETIK_DIZINI")"
BACKUP_DIR="${BACKUP_DIR:-/srv/linkyoself/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
ZAMAN="$(date -u +%Y%m%dT%H%M%SZ)"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }

compose() {
    docker compose --project-directory "$DEPO" \
        -f "$DEPO/docker-compose.yml" -f "$DEPO/deploy/docker-compose.prod.yml" "$@"
}

mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"

# Herhangi bir adim duserse (set -e) yarim kalan .tmp dosyalari kalmasin.
trap 'rm -f "$BACKUP_DIR"/db-"$ZAMAN".dump.tmp "$BACKUP_DIR"/media-"$ZAMAN".tgz.tmp' EXIT

# --- Veritabani ------------------------------------------------------------
# Once gecici ada yaziliyor, dogrulaninca yeniden adlandiriliyor: yarida
# kalmis bir dosya hicbir zaman gecerli bir yedek gibi gorunmuyor.
DB_DOSYA="db-$ZAMAN.dump"
log "veritabani -> $DB_DOSYA"
# Tek tirnak bilerek: degiskenler KONTEYNERIN icinde (Postgres imajinin
# kendi ortaminda) acilmali, sunucudaki kabukta degil.
# shellcheck disable=SC2016
# </dev/null: `compose exec` stdin'i konteynere aktariyor (-T yalnizca TTY'yi
# kapatiyor). deploy.sh bu betigi `ssh ... bash -s` ile pipe'tan okunan bir
# betigin icinden cagiriyor; stdin acik kalsaydi docker o betigin geri
# kalanini yutardi.
compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' < /dev/null > "$DB_DOSYA.tmp"

# Bos ya da bozuk bir dosya "yedek alindi" saniliyordu; pg_restore'un
# icindekiler listesini okuyabilmesi dosyanin butun oldugunu gosteriyor.
if ! compose exec -T db pg_restore --list < "$DB_DOSYA.tmp" > /dev/null; then
    rm -f "$DB_DOSYA.tmp"
    log "HATA: dokum okunamadi, yedek silindi"
    exit 1
fi
mv "$DB_DOSYA.tmp" "$DB_DOSYA"
chmod 600 "$DB_DOSYA"
log "veritabani tamam ($(du -h "$DB_DOSYA" | cut -f1))"

# --- Avatarlar -------------------------------------------------------------
MEDIA_DOSYA=""
MEDIA_BIRIMI="$(compose config --format json | jq -r '.volumes.media.name // empty' 2>/dev/null || true)"
MEDIA_BIRIMI="${MEDIA_BIRIMI:-linkyoself_media}"
if docker volume inspect "$MEDIA_BIRIMI" > /dev/null 2>&1; then
    MEDIA_DOSYA="media-$ZAMAN.tgz"
    log "avatarlar ($MEDIA_BIRIMI) -> $MEDIA_DOSYA"
    # --user: dosya cagiranin (deploy) olsun. Konteyner root olarak yazsaydi
    # asagidaki chmod EPERM ile duser ve set -e butun yedegi basarisiz
    # sayardi. Avatarlar herkese okunabilir (api 10001 olarak yaziyor).
    docker run --rm --user "$(id -u):$(id -g)" -v "$MEDIA_BIRIMI:/kaynak:ro" -v "$BACKUP_DIR:/hedef" alpine \
        tar czf "/hedef/$MEDIA_DOSYA.tmp" -C /kaynak .
    mv "$MEDIA_DOSYA.tmp" "$MEDIA_DOSYA"
    chmod 600 "$MEDIA_DOSYA"
    log "avatarlar tamam ($(du -h "$MEDIA_DOSYA" | cut -f1))"
else
    log "avatar birimi yok (S3 deposu ya da henuz yukleme yok); atlandi"
fi

# --- Uzak kopya ------------------------------------------------------------
if [ -n "$RCLONE_REMOTE" ]; then
    log "uzak kopya -> $RCLONE_REMOTE"
    rclone copy "$DB_DOSYA" "$RCLONE_REMOTE/"
    [ -z "$MEDIA_DOSYA" ] || rclone copy "$MEDIA_DOSYA" "$RCLONE_REMOTE/"
fi

# --- Eski yedekler -----------------------------------------------------------
# Yalnizca yerel kopyalar siliniyor; uzaktakilerin omrunu kovanin kendi
# yasam dongusu kurali belirlemeli (yanlis bir betik uzak yedekleri de
# silemesin).
silinen=$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'media-*.tgz' \) -mtime +"$KEEP_DAYS" -print -delete | wc -l)
log "eski yedek silindi: $silinen (>${KEEP_DAYS} gun)"
log "bitti"
