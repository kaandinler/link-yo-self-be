# GOAL: Bloklarla kurulan profil sayfasi (surukle-birak editor)

Durum: onaylandi (Kaan, 2026-10-25). Uygulama sirasi ve PR'lar:
`docs/ROADMAP.md`, "Siradaki" bolumundeki `blok-*` maddeleri.

## Neden

Bugun profil sayfasi sabit bir sirayla ciziliyor: ust kisim (avatar, ad,
bio, sosyal ikonlar), altinda linkler, en altta imza. Kullanicinin
degistirebildigi tek sey linklerin sirasi ve renkler. Farklilasma noktasi:
kullanici sayfasini bloklardan kurar -- metin, gomulu video/muzik,
ayirici, linkler -- surukleyip siralar, yanda canli onizlemeyi gorur.

## Kapsam (v1)

Ust kisim (avatar, ad, bio) v1'de BLOK DEGIL; sabit kaliyor. Bloklar
onun altinda, imzanin ustunde.

| Tip | Ayar (config) | Not |
|---|---|---|
| `link` | yok; `link_id` | Mevcut `links` satirina referans. Baslik, adres, renkler, tiklama sayaci, analitik orada kaliyor. |
| `text` | `{ "baslik"?: str<=80, "metin"?: str<=1000 }` | YALNIZCA duz metin. HTML/markdown yok; satir sonlari korunur. |
| `social` | yok | Mevcut sosyal hesaplari ikon satiri olarak cizer. Ust kisimdaki ikonlar bu blok VARSA oradan kalkar (iki kez cizilmesin). |
| `embed` | `{ "saglayici": "youtube"\|"spotify", "kimlik": str }` | Adres kullanicidan alinir, SUNUCUDA ayristirilir; saklanan yalnizca saglayici + kimlik. Bkz. Guvenlik. |
| `divider` | `{ "stil": "cizgi"\|"bosluk" }` | |

Her blokta: `id`, `type`, `order_index`, `is_visible`, `config` (JSON), `link_id` (yalnizca `link`).

## Veri modeli (backend)

Yeni tablo `page_blocks`:

- `user_id` FK users, CASCADE
- `type` String(20), CHECK ile v1 tipleri
- `order_index` Integer
- `is_visible` Boolean, varsayilan true
- `config` JSON, nullable
- `link_id` FK links, **CASCADE** (link silinince blogu da gider), nullable;
  `type='link'` iken zorunlu, digerlerinde NULL (CHECK)
- `(user_id, link_id)` UNIQUE: ayni link iki kez yerlestirilemez

`config` her tip icin AYRI bir Pydantic semasiyla dogrulanir (discriminated
union, `type` alanina gore). Sema disi alan reddedilir (`extra="forbid"`):
`extra_settings`'teki "icerigini istemci belirliyor, kazara yayinlanir"
riski burada tekrarlanmasin.

Sinirlar: kullanici basina en fazla 100 blok; `text.metin` 1000 karakter.

### Migration

Her kullanici icin, mevcut gorunumu AYNEN koruyacak bloklar:
1. Aktif ve pasif butun linkleri `order_index` sirasiyla `link` blogu
   olarak (`is_visible` = link'in `is_active`'i).
2. `social` blogu YARATILMAZ: ikonlar ust kisimda kalmaya devam eder.
   Kullanici isterse ekler.

Migration'dan sonra hicbir profil sayfasi gorsel olarak degismemeli
(blok-public adiminda e2e ile dogrulanacak).

### Linklerle uyum (gecis donemi)

Eski uclar calismaya devam eder, frontend gecis boyunca kirilmaz:
- `POST /links` linki yaratir VE sona bir `link` blogu ekler (ayni islemde).
- `DELETE /links/{id}` -> blok CASCADE ile gider.
- `POST /links/reorder` link bloklarinin sirasini, diger bloklarin
  arasindaki yerlerini koruyarak gunceller. (Editor yayina girince
  `/blocks/reorder` asil uc olur; eski uc bir sure kalir.)

## API

Sahibi icin (`get_current_user`):

- `GET /v1/blocks` -> sirali liste (link bloklarinda link'in kendisi gomulu)
- `POST /v1/blocks` -> yeni blok (`link` tipi bu uctan yaratilmaz; link
  `POST /links` ile yaratilir)
- `PATCH /v1/blocks/{id}` -> config / is_visible
- `DELETE /v1/blocks/{id}` -> `link` tipinde 409 (link'i silmek icin
  `/links`; blok gizlenebilir)
- `POST /v1/blocks/reorder` -> `{ "ids": [..] }`; liste kullanicinin
  butun bloklarini TAM olarak icermeli (eksik/fazla/baskasinin -> 422)

Herkese acik profil (`GET /v1/p/{username}`): yanita `blocks` eklenir
(yalnizca `is_visible`, link bloklarinda yalnizca aktif linkler). `links`
alani gecis boyunca kalir.

Her mutasyon profil onbellegini temizler (mevcut vekil mekanizmasi
`/v1/blocks` yollarini da kapsamali).

## Guvenlik

- **Embed:** kullanici iframe adresi YAZAMAZ. Uc verilen adresi
  ayristirir; yalnizca bilinen kaliplar kabul edilir
  (`youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`,
  `open.spotify.com/{track,album,playlist,episode}/`), kimlik
  `^[A-Za-z0-9_-]{6,64}$`. Iframe adresi FRONTEND'de sabit sablondan
  uretilir (`https://www.youtube-nocookie.com/embed/{kimlik}`,
  `https://open.spotify.com/embed/{tur}/{kimlik}`).
  `sandbox` + `allow` listesi dar; `referrerpolicy="strict-origin-when-cross-origin"`;
  `loading="lazy"`.
- **CSP:** sitede iframe izni yalnizca bu iki saglayiciya (`frame-src`).
  CSP yoksa bu adimda eklenir, varsa genisletilir.
- **Metin:** React metin olarak cizer (`dangerouslySetInnerHTML` YOK).
- **Gizlilik:** youtube-nocookie; profil sahibinin ziyaretcileri
  gomulu oynaticiyi tiklamadan once ucuncu tarafa cerez gondermesin
  diye v1'de "tikla-yukle" (ilk tiklamaya kadar yalnizca kapak + buton)
  degerlendirilecek; olcum blok-embed PR'inda.

## Frontend

### Public sayfa (blok-public)
`blocks` varsa onlardan cizilir; yoksa (eski backend) `links`'ten. Gorunum
mevcut link karti ile birebir ayni kalir.

### Editor (blok-editor)
- `/[language]/profile/page-editor` (ya da mevcut `/links` sayfasinin
  yerine; karar PR'da, gerekcesiyle).
- Sol: blok listesi, `@dnd-kit/sortable` ile surukle-birak. Klavye ile
  siralama (dnd-kit'in klavye sensoru) VE mevcut yukari/asagi butonlari
  kalir -- `/links` sayfasindaki erisilebilirlik kararinin gerekcesi
  ayni (isaretleyici olmayan cihazlar).
- Sag: canli onizleme, public sayfanin AYNI bilesenleriyle (iki kopya
  olmasin).
- "Blok ekle" menusu: tip secimi -> tipine ozel form.
- Iyimser guncelleme (react-query), hata olursa geri al + snackbar.
- TR/EN ceviriler.
- a11y Playwright testi (axe) editor icin.

## Bolunmus PR'lar

1. **blok-model** (be): tablo, migration (+ geri alma), semalar, CRUD +
   reorder uclari, link uclariyla uyum, testler (migration'in mevcut
   gorunumu korudugu dahil).
2. **blok-public** (be + fe): public profil yanitina `blocks`; sayfa
   bloklardan ciziliyor; e2e: migration sonrasi sayfa ayni.
3. **blok-editor** (fe): surukle-birak editor + onizleme; yalnizca mevcut
   tipler (`link`, `social`, `divider`).
4. **blok-metin** (be + fe): `text` tipi.
5. **blok-embed** (be + fe): `embed` tipi, CSP, tikla-yukle olcumu.

Her PR kendi basina calisir durumda birakir; bir sonrakine baglanmadan
merge edilebilir.

## Kapsam disi (v1)

- Ust kismin (avatar/ad/bio) blok olmasi
- Iki sutunlu/serbest yerlesim, blok basina renk/stil
- E-posta toplama, form, odeme bloklari
- Blok sablonlari (tema sablonlari ayri bir is: `tema-sablonlari`)
