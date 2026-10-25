# LinkYoSelf — ROADMAP

Tek kaynak bu dosya. `pm` agent'i yonetiyor (bkz. `docs/AGENTS.md`);
insan da elle duzenleyebilir. Her madde tek PR'lik olmali.

Hedef: uygulamayi en ucuz yoldan production'a cikarmak --
tek VPS (Hetzner CX23) + mevcut docker-compose + Caddy (otomatik TLS),
domain Cloudflare'de.

## Kaan'in karari bekleniyor

- **Domain adi.** Henuz alinmadi. Butun dosyalar `${DOMAIN}` kullaniyor;
  karar verilince yalnizca sunucudaki `.env` degisiyor.
- **SMTP saglayicisi.** Prod'da e-posta dogrulama ve sifre sifirlama icin
  gerekli (`SMTP_HOST` bossa e-posta log'a yaziliyor, kullaniciya gitmiyor).
  Secenekler: Resend, Brevo, Amazon SES, Mailgun -- hepsinin dusuk hacimde
  ucretsiz/ucuz katmani var. Domain alininca SPF/DKIM kayitlari eklenecek.
- **Uptime izleme.** Ucretsiz katmanli bir dis kontrol (UptimeRobot,
  Better Stack, healthchecks.io) `https://${DOMAIN}` ve `https://api.${DOMAIN}`'i
  izlesin. Hesap acmak insan isi.
- **Off-site backup hedefi.** `deploy/backup.sh` yerel kopya tutuyor;
  sunucu kaybina karsi Cloudflare R2 (10 GB'a kadar ucretsiz) onerisi.

## Simdi

_(pm agent'i siradaki isi buraya yazar)_

## Siradaki

1. **istemci-ip** (be + fe) — **URETIMI BLOKLUYOR, tasarimi Kaan onaylamali.**

   Sorun: frontend'in butun API cagrilari (`src/services/api/config.ts`:
   `API_URL = "/api/proxy"`) ve giris (`/api/auth/session`) Next SUNUCUSU
   uzerinden backend'e gidiyor ve istemcinin IP'si iletilmiyor. Backend'in
   gordugu adres her kullanici icin ayni: web konteyneri. Hiz sinirinin IP
   katmani (`core/rate_limit/kurallar.py`) butun site icin TEK sayaca
   dusuyor:
   - `GIRIS_IP` (15 dk'da 20 basarisiz): sitedeki herhangi biri 20 yanlis
     sifre girince 15 dakika boyunca HERKESIN girisi 429 aliyor.
   - `KAYIT_IP` (saatte 5): butun site saatte 5 hesap acabiliyor.
   - `SIFIRLAMA_IP` (saatte 5): butun site saatte 5 sifirlama e-postasi.
   E2E bunu yakalamiyor cunku orada hiz siniri kapali; backend suiti
   dogrudan backend'e istek attigi icin yakalamiyor. Uretim katmanindan
   (#46) bagimsiz, mevcut bir sorun; dev ortaminda da var ama orada tek
   kullanici oldugu icin gorunmuyor.

   Onerilen tasarim (iki secenek, ikisi de once dogrulanmali):
   - **A (onerilen): Next -> backend yigin icinden.** `API_URL=http://api:8000/api`.
     Next, Caddy'nin ona verdigi `X-Forwarded-For`'u (Caddy guvenilmeyen
     istemcinin gonderdigini atip gercek adresi yaziyor) ve
     `X-Forwarded-Proto: https`'i backend'e iletir. Backend'de
     `ALLOWED_HOSTS`'a `api` eklenir (port disari kapali oldugu icin
     disaridan bu Host'la gelinemiyor). `TRUSTED_PROXY_COUNT=1` iki yolda da
     dogru adresi veriyor: tarayici -> Caddy -> api ve tarayici -> Caddy ->
     Next -> api. Dokunulacak yer: Next'te sunucu tarafinda backend'e giden
     her `fetch` (vekil, oturum, profil sayfasi, onbellek temizleme) -- ortak
     bir yardimciya toplanmali.
   - **B: Caddy uzerinden, `trusted_proxies` ile.** Caddy'ye yalnizca web
     konteynerinin SABIT IP'sine guvenmesi soylenir (sabit alt agli ozel bir
     ag), api sitesinde `X-Forwarded-For {client_ip}`. Daha az Next kodu ama
     Caddy'nin `trusted_proxies`/`trusted_proxies_strict` davranisina bagli
     ve genis bir ozel aralik (`private_ranges`) GUVENLI DEGIL: IPv6 ile
     gelen istekler docker-proxy uzerinden Docker'in gecit adresiyle (ozel
     aralik) gorunebilir ve sahte `X-Forwarded-For` kabul edilir.

   Kabul kriterleri: iki farkli istemci IP'sinden Next uzerinden gelen
   basarisiz girisler AYRI sayilmali; istemcinin kendi yazdigi
   `X-Forwarded-For` hicbir yolda sayaci etkilememeli; bunu gercek yigin
   (Caddy dahil) uzerinde olcen bir test.
2. **prod-smoke** — deploy sonrasi uctan uca duman testi betigi: kayit -> giris ->
   link ekle -> public sayfa -> tiklama sayaci. Deploy workflow'una adim olarak.
3. **prod-oncesi-tarama** — production'dan once kapanmasi gereken aciklar:
   olu kod, eksik test, admin uclarinin yetki testleri, hata sayfalari.

Acik PR'lar (merge sirasi): #46 deploy-compose -> #47 deploy-sunucu -> #48 deploy-cd.
Log rotasyonu #46'nin icinde.

## Bitti

- Ozellik seti MVP'yi gecti: auth, e-posta dogrulama, sifre sifirlama, link/sosyal
  hesap CRUD, `@username` public sayfa + OG karti, analytics, avatar (local/S3),
  hiz siniri (Redis), admin, TR/EN. Docker yigini (#41/#89), avatar (#43/#91).
