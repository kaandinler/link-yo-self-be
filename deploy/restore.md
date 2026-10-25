# Yedekten geri yukleme

Yedekleri `deploy/backup.sh` uretiyor (bkz. betigin basi): `BACKUP_DIR`
altinda `db-<zaman>.dump` ve `media-<zaman>.tgz`. Komutlarin hepsi
sunucuda, `deploy` kullanicisi olarak ve deponun kokunden:

```bash
cd /srv/linkyoself/link-yo-self-be
alias dc='docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml'
```

## 1. Yazanlari durdur

```bash
dc stop api web
```

`db` ve `redis` acik kaliyor. Geri yukleme sirasinda kayit ya da tiklama
gelmesin; gelirse yarim bir durumun ustune yazilir.

## 2. Veritabani

```bash
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
    < /srv/linkyoself/backups/db-20261025T031500Z.dump
```

- `--clean --if-exists`: mevcut tablolari once siliyor; bos bir
  veritabaninda da hata vermiyor (ikisi de denendi).
- `--no-owner`: dokumdeki sahiplik bilgisi uygulanmiyor; yeni sunucuda
  kullanici adi farkli olsa bile calisiyor.
- `alembic_version` tablosu da yedekte. Yedek eski bir surumdense:

  ```bash
  dc run --rm migrate
  ```

## 3. Avatarlar (yalnizca STORAGE_BACKEND=local)

```bash
docker run --rm -v linkyoself_media:/hedef -v /srv/linkyoself/backups:/yedek:ro alpine \
    sh -c 'rm -rf /hedef/* && tar xzf /yedek/media-20261025T031500Z.tgz -C /hedef && chown -R 10001 /hedef'
```

`chown 10001`: api konteyneri root olmayan `app` kullanicisiyla (uid 10001)
calisiyor ve bu dizine yaziyor.

## 4. Baslat ve dogrula

```bash
dc start api web
dc ps
curl -fsS https://api.$DOMAIN/ && echo
```

Bir hesapla giris yapip bir profil sayfasini acin.

## Olculen (yerelde, Postgres 16)

Gecis sirasinda calisan sema (butun migration'lar) + 3 kullanici + 20
platform kaydi:

| Adim | Sonuc |
|---|---|
| `pg_dump -Fc` | 68 KB, 0.08 sn |
| `pg_restore --list` (backup.sh'in butunluk kontrolu) | gecti |
| Tablolar doluyken `--clean --if-exists` ile geri yukleme | 0.12 sn, kullanicilar geri geldi (0 -> 3) |
| Bos bir veritabanina ayni komut | hatasiz, 3 kullanici |
| Geri yuklemeden sonra `alembic current` | `(head)` |

Sunucuda ilk yedek alindiktan sonra bu tabloyu gercek verilerle bir kez
tekrarlayin: denenmemis yedek, yedek degildir.

## Uzak kopya (istege bagli)

Sunucunun kendisi kaybolursa yerel yedekler de gider. Cloudflare R2
(10 GB'a kadar ucretsiz) icin:

```bash
sudo apt-get install -y rclone
rclone config            # "s3" -> saglayici "Cloudflare" -> R2 erisim anahtarlari
```

Sonra cron satirina `RCLONE_REMOTE=r2:<kova-adi>` ekleyin. Kovaya bir
yasam dongusu kurali (ornegin 30 gun) koyun; betik uzaktaki dosyalari
bilerek silmiyor.
