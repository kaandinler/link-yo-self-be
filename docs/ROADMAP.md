# LinkYoSelf — ROADMAP

Tek kaynak bu dosya. `pm` agent'i yonetiyor (bkz. `docs/AGENTS.md`);
insan da elle duzenleyebilir. Her madde tek PR'lik olmali.

Hedef (2026-10-25, Kaan): **once urunu farklilastirmak, sonra production.**
Uretim altyapisi hazir ve `dev`'de (tek VPS + docker-compose + Caddy,
`docs/DEPLOY.md`); yayin, asagidaki urun isleri olgunlasinca. Bu yuzden
`Siradaki` listesi YAZILDIGI SIRAYLA yurutulur; "production'i bloklayan
is" onceligi simdilik yalnizca guvenlik aciklari icin gecerli.

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

Bloklar sisteminin tam tasarimi: `docs/goals/bloklar.md` (onaylandi). Her
`blok-*` maddesi oradaki "Bolunmus PR'lar" listesinin bir adimi; task
yazarken pm o dosyadan alir, ship o dosyaya uyar.

1. **blok-model** (be) — `page_blocks` tablosu, migration (mevcut gorunumu
   koruyarak, geri alinabilir), tip basina Pydantic semalari, `/v1/blocks`
   CRUD + reorder, `/links` uclariyla uyum. Bkz. goal dosyasi.
2. **qr-kod** (fe) — Pano/profil duzenleme ekraninda profil adresinin QR
   kodu: goruntule + PNG/SVG indir. Tamamen istemcide uretilir (yeni bir
   backend ucu yok, adres disari gonderilmez). Kutuphane: `qrcode` (MIT,
   bagimliliksiz) -- ya da esdegeri; secim ve paket boyutu PR'da olculur.
   Adres `NEXT_PUBLIC_SITE_URL`'den, dil oneki olmadan (`/kullanici`).
3. **blok-public** (be + fe) — public profil yanitina `blocks`; sayfa
   bloklardan; e2e: migration sonrasi sayfa gorsel olarak ayni.
4. **tema-sablonlari** (fe, gerekirse be) — Customize sayfasinda hazir
   temalar (6-8 tane): tek tiklamayla `theme_color` + `background_type` +
   `background_value` ayarlanir, onizlemesi gorunur, sonra elle
   degistirilebilir. Sablonlar kodda sabit bir liste (veritabani degil).
   Kontrast: her sablonda metin/arka plan orani WCAG AA (4.5:1) -- testte
   olculur. Yeni alan gerekmiyorsa backend'e dokunulmaz.
5. **blok-editor** (fe) — `@dnd-kit/sortable` ile surukle-birak + klavye +
   yukari/asagi butonlari, canli onizleme (public sayfanin ayni
   bilesenleri), `link`/`social`/`divider` tipleri, a11y testi.
6. **zamanli-linkler** (be + fe) — Linke istege bagli `starts_at` / `ends_at`
   (UTC saklanir, formda kullanicinin saat diliminde gosterilir). Public
   profil yalnizca simdi araliktaki linkleri dondurur; panoda "zamanlanmis"
   / "suresi doldu" etiketi. DIKKAT: profil sayfasi onbellekte (60 sn
   tavan) -- bir linkin acilma/kapanma ani en fazla o kadar gecikir;
   kabul ediliyor mu yoksa onbellek suresi sonraki sinira gore mi
   kisaltilir, PR'da olculup yazilir. Tiklama ucu da suresi dolmus
   linke yonlendirmemeli.
7. **blok-metin** (be + fe) — `text` blok tipi.
8. **blok-embed** (be + fe) — `embed` blok tipi (YouTube, Spotify), CSP,
   tikla-yukle olcumu.
9. **prod-oncesi-tarama (devami)** — ilk tarama (2026-10-25) temiz cikti: dev'de
   BE testleri, FE lint/typecheck ve e2e yesil; admin uclari `is_admin` ile
   korunuyor ve testli. Geriye kalan: hata sayfalarinin (500/404) uretim
   derlemesinde elle kontrolu, `@faker-js/faker`'in `dependencies` yerine
   `devDependencies`'e alinmasi (istemci paketine girip girmedigi olculmeli).

## Fikir havuzu (siraya alinmadi)

- **Link detay sayfasi** — analitikte linke tiklayinca o linkin buyuk grafigi
  ve kaynak (referrer) dagilimi. Not: link bazinda gunluk grafikler ZATEN var
  (`/analytics/timeseries/by-link`, `link-sparkline.tsx`); bu onun ileri hali.

## Bitti

- **prod-swagger** (#51): uretimde `/docs`, `/redoc`, `/openapi.json` kapali (Kaan onayladi);
  gelistirmede acik. `tests/test_api_docs.py`.
- **istemci-ip** (#50, FE #94): vekil ve oturum ucu backend'e
  yigin icinden (`API_URL_INTERNAL`) ve istemcinin `X-Forwarded-For`'uyla gidiyor;
  hiz sinirinin IP katmani artik istemci basina. Tasarim A, Kaan onayladi. Olcum
  README'de ("Frontend'in iki API adresi").
- Uretim hazirligi: agent sistemi (#45, FE #93), prod katmani + Caddy (#46), sunucu
  kurulumu + yedek (#47), onayli yayin + geri donus (#48), duman testi (#49).

- Ozellik seti MVP'yi gecti: auth, e-posta dogrulama, sifre sifirlama, link/sosyal
  hesap CRUD, `@username` public sayfa + OG karti, analytics, avatar (local/S3),
  hiz siniri (Redis), admin, TR/EN. Docker yigini (#41/#89), avatar (#43/#91).
