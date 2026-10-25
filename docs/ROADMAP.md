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

1. **deploy-compose** — `deploy/docker-compose.prod.yml` (override), `deploy/Caddyfile`,
   `deploy/.env.prod.example`. Caddy 80/443, api/web portlari disari kapali.
2. **deploy-sunucu** — `deploy/bootstrap-server.sh` (deploy kullanicisi, ufw, docker,
   swap, unattended-upgrades) + `deploy/backup.sh` + `deploy/restore.md`.
3. **deploy-cd** — `.github/workflows/deploy.yml` (yalnizca elle, `production`
   environment onayiyla) + `docs/DEPLOY.md` runbook.
4. **prod-smoke** — deploy sonrasi uctan uca duman testi betigi: kayit -> giris ->
   link ekle -> public sayfa -> tiklama sayaci. Deploy workflow'una adim olarak.
5. **log-rotasyon** — Docker json-file log'larina boyut siniri (CX23 diski 40 GB).
6. **prod-oncesi-tarama** — production'dan once kapanmasi gereken aciklar:
   olu kod, eksik test, admin uclarinin yetki testleri, hata sayfalari.

## Bitti

- Ozellik seti MVP'yi gecti: auth, e-posta dogrulama, sifre sifirlama, link/sosyal
  hesap CRUD, `@username` public sayfa + OG karti, analytics, avatar (local/S3),
  hiz siniri (Redis), admin, TR/EN. Docker yigini (#41/#89), avatar (#43/#91).
