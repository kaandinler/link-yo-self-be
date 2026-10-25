# Uretime alma (runbook)

Hedef: tek bir VPS (Hetzner CX23, Ubuntu LTS) uzerinde mevcut
docker-compose yigini + Caddy (otomatik TLS). Alan adi ve DNS Cloudflare'de.

| Parca | Dosya |
|---|---|
| Uretim katmani | `deploy/docker-compose.prod.yml`, `deploy/Caddyfile` |
| Ayar sablonu | `deploy/.env.prod.example` |
| Sunucu ilk kurulum | `deploy/bootstrap-server.sh` |
| Yayin + geri donus | `deploy/deploy.sh`, `.github/workflows/deploy.yml` |
| Yedek / geri yukleme | `deploy/backup.sh`, `deploy/restore.md` |

Asagidaki her adim insan isi; agent'lar sunucuya ve uretime dokunmuyor
(bkz. `docs/AGENTS.md`).

## 0. Bir kez: hesaplar

1. **Alan adi:** Cloudflare Registrar'dan alin. DNS Cloudflare'de kalsin.
2. **Sunucu:** Hetzner Cloud -> CX23, Ubuntu 24.04, **SSH anahtariyla**
   (parola degil). Konum: Almanya/Finlandiya.
3. **E-posta (SMTP):** Resend/Brevo/SES'ten biri. Alan adini dogrulayin
   (SPF/DKIM kayitlari saglayicinin verdigi gibi Cloudflare DNS'e).

## 1. DNS

Cloudflare DNS'te, sunucunun IPv4'u icin uc **A** kaydi:

| Ad | Icerik | Proxy |
|---|---|---|
| `@` | sunucu IP | **DNS only (gri bulut)** |
| `www` | sunucu IP | DNS only |
| `api` | sunucu IP | DNS only |

**Neden gri bulut:** Caddy sertifikayi Let's Encrypt'in HTTP-01
dogrulamasiyla aliyor; turuncu bulut (Cloudflare proxy) bu istegi araya
girip karsiliyor. Ayrica proxy acikken backend'in gordugu adres
Cloudflare'in olur ve `TRUSTED_PROXY_COUNT=1` yanlis adresi sayar.
Proxy'yi ileride acmak istenirse: `TRUSTED_PROXY_COUNT=2` ve Cloudflare
SSL modu "Full (strict)".

Kontrol: `dig +short api.<alan-adi>` sunucu IP'sini donmeli.

## 2. Sunucu

```bash
ssh root@<sunucu-ip>
curl -fsSLO https://raw.githubusercontent.com/kaandinler/link-yo-self-be/main/deploy/bootstrap-server.sh
less bootstrap-server.sh
bash bootstrap-server.sh
```

Bitince **yeni bir terminalde** `ssh deploy@<sunucu-ip>` ile girebildiginizi
dogrulayin; root oturumunu ondan sonra kapatin.

## 3. Ayarlar

```bash
ssh deploy@<sunucu-ip>
cd /srv/linkyoself/link-yo-self-be
cp deploy/.env.prod.example .env && chmod 600 .env
nano .env     # DOMAIN, ACME_EMAIL, SECRET_KEY, POSTGRES_PASSWORD, SMTP_*
```

`SECRET_KEY` ve `POSTGRES_PASSWORD` icin sablondaki `python3 -c ...`
komutlari. Bu dosya sunucudan baska hicbir yerde durmasin.

## 4. Ilk yayin (elle)

Ilk seferde sertifika alinmasini ve migration'i gozle gormek icin:

```bash
alias dc='docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml'
dc up -d --build          # ilk derleme 5-10 dk (Next)
dc ps                     # hepsi running/healthy
dc logs -f caddy          # "certificate obtained successfully" (x3: @, www, api)
```

Ilk admin:

```bash
dc run --rm api python -m scripts.create_admin \
    --username <ad> --email <e-posta> --password '<parola>'
```

Tarayicida `https://<alan-adi>` -> kayit ol -> e-posta dogrulama geldi mi
-> link ekle -> `https://<alan-adi>/<kullanici-adi>` acildi mi.

## 5. Yedek

```bash
crontab -e
# her gece 03:15 UTC
15 3 * * * /srv/linkyoself/link-yo-self-be/deploy/backup.sh >> /srv/linkyoself/backups/backup.log 2>&1
```

Bir kez elle calistirin ve `deploy/restore.md`'deki geri yuklemeyi
**deneyin**. Uzak kopya (R2) icin ayni dosyanin son bolumu.

## 6. Sonraki yayinlar: GitHub Actions

Bir kez:

1. Yalnizca bu is icin anahtar:
   ```bash
   ssh-keygen -t ed25519 -f linkyoself-deploy -N "" -C github-actions
   ssh-copy-id -i linkyoself-deploy.pub deploy@<sunucu-ip>
   ssh-keyscan -t ed25519 <DEPLOY_HOST>   # -> DEPLOY_KNOWN_HOSTS
   # DIKKAT: DEPLOY_HOST'a ne yazacaksaniz (IP ya da ad) AYNISIYLA tarayin;
   # known_hosts satiri o ada bagli, farkliysa ssh baglanmayi reddeder.
   ```
2. GitHub -> backend deposu -> Settings -> Environments -> **New environment: `production`**
   - **Required reviewers:** kendiniz
   - **Deployment branches:** yalnizca `main`
   - Secrets: `DEPLOY_HOST`, `DEPLOY_USER` (`deploy`), `DEPLOY_SSH_KEY`
     (ozel anahtarin icerigi), `DEPLOY_KNOWN_HOSTS` (keyscan ciktisi)
   - Variable (istege bagli): `DOMAIN`
3. Yerel `linkyoself-deploy` ozel anahtarini silin; artik yalnizca GitHub'da.

Her yayin:

1. `dev` -> `main` PR'ini merge edin (FE ve BE).
2. Actions -> **Deploy** -> Run workflow (`main`, `fe_ref`: `origin/main`).
3. Onay isteyen isi onaylayin.

`deploy/deploy.sh` sirasiyla: yedek -> iki depoyu istenen surume al ->
imajlari derle (calisan site etkilenmez) -> `up -d` -> saglik kontrolu.
Derleme duserse calisan surume dokunulmuyor; yayin ya da saglik kontrolu
duserse onceki surume donuluyor ve is kirmizi bitiyor.

**Geri donus migration'lari geri almiyor.** Bkz. betigin basi; uyumsuz
bir migration sonrasi `deploy/restore.md`.

## Sorun giderme

| Belirti | Sebep / cozum |
|---|---|
| Caddy log'unda `challenge failed` / sertifika yok | DNS henuz yayilmadi ya da turuncu bulut acik. `dig` ile kontrol, gri bulut. 80 acik mi (`ufw status`). Cok deneme Let's Encrypt'in haftalik sinirina takilabilir: duzeltip bekleyin. |
| API her istekte 307 / tarayicida "too many redirects" | `FORWARDED_ALLOW_IPS` uygulanmamis. Prod katmani olmadan mi kaldirildi? `dc config \| grep FORWARDED` |
| API 400 "Invalid host header" | Host `ALLOWED_HOSTS`'ta degil. `.env`'deki `DOMAIN` ile DNS'teki ad ayni mi? |
| Tarayici konsolunda CORS hatasi | `ALLOWED_ORIGINS` = `https://DOMAIN`. www'den mi geliniyor? (www kendiliginden ana alana yonleniyor.) |
| Profil sayfasi 500, web log'unda `fetch failed` | web, `https://api.DOMAIN`'e ulasamiyor: caddy ayakta mi, sertifika alindi mi. |
| `docker compose up` "POSTGRES_PASSWORD tanimli degil" | `.env` deponun KOKUNDE olmali, `deploy/` altinda degil. |
| Disk doluyor | `docker system df`; eski imajlar `docker image prune -a`. Log'lar 3x10 MB ile sinirli. |
| Sunucu `apt` guncellemesi sonrasi yeniden baslatma istiyor | `ssh root@<sunucu-ip> reboot` (deploy'un sudo yetkisi yok; root yalnizca anahtarla girebiliyor) -- konteynerler `restart: unless-stopped` ile geri geliyor. |

Log okuma:

```bash
dc logs --tail 100 api
dc logs -f web
dc logs caddy | grep -i error
```
