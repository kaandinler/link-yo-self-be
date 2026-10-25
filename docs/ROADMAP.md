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
- **Uretimde Swagger (`/docs`, `/redoc`, `/openapi.json`).** Su an uretimde de
  acik: butun uclarin listesi herkese gorunuyor. Gizlilik saglamaz (uclar
  zaten tarayicidan gorulebilir) ama saldiri yuzeyini kesfetmeyi kolaylastirir.
  Secenekler: kapat (`ENVIRONMENT=production`'da `docs_url=None`), acik birak,
  ya da yalnizca admin'e ac.
- **Off-site backup hedefi.** `deploy/backup.sh` yerel kopya tutuyor;
  sunucu kaybina karsi Cloudflare R2 (10 GB'a kadar ucretsiz) onerisi.

## Simdi

_(pm agent'i siradaki isi buraya yazar)_

## Siradaki

1. **prod-oncesi-tarama (devami)** — ilk tarama (2026-10-25) temiz cikti: dev'de
   BE testleri, FE lint/typecheck ve e2e yesil; admin uclari `is_admin` ile
   korunuyor ve testli. Geriye kalan: hata sayfalarinin (500/404) uretim
   derlemesinde elle kontrolu, `@faker-js/faker`'in `dependencies` yerine
   `devDependencies`'e alinmasi (istemci paketine girip girmedigi olculmeli).

## Bitti

- **istemci-ip** (be + fe, dal `claude/istemci-ip`): vekil ve oturum ucu backend'e
  yigin icinden (`API_URL_INTERNAL`) ve istemcinin `X-Forwarded-For`'uyla gidiyor;
  hiz sinirinin IP katmani artik istemci basina. Tasarim A, Kaan onayladi. Olcum
  README'de ("Frontend'in iki API adresi").
- Uretim hazirligi: agent sistemi (#45, FE #93), prod katmani + Caddy (#46), sunucu
  kurulumu + yedek (#47), onayli yayin + geri donus (#48), duman testi (#49).

- Ozellik seti MVP'yi gecti: auth, e-posta dogrulama, sifre sifirlama, link/sosyal
  hesap CRUD, `@username` public sayfa + OG karti, analytics, avatar (local/S3),
  hiz siniri (Redis), admin, TR/EN. Docker yigini (#41/#89), avatar (#43/#91).
