# LinkYoSelf API

Linktree benzeri bir "link in bio" servisinin FastAPI backend'i.
Kullanicilar kayit olur, profillerini duzenler, linklerini yonetir ve
`/{username}` adresinde herkese acik bir link sayfasina sahip olur.

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # gelistirme icin: requirements-dev.txt

cp .env.example .env                   # DATABASE_URL ve SECRET_KEY'i doldurun
alembic upgrade head

uvicorn main:app --reload
```

Swagger arayuzu: <http://localhost:8000/docs>

> **Not:** `bcrypt` 4.0.1'e pinlenmistir. `passlib` 1.7.4 bcrypt >= 4.1 ile
> uyumsuzdur ve yukseltilirse kayit ucu 500 doner.

### Ilk admin

```bash
python -m scripts.create_admin --username kaan \
    --email kaan@example.com --password 'Gizli.Parola1'

# ya da ortam degiskenleriyle (CI icin daha rahat):
ADMIN_USERNAME=... ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m scripts.create_admin
```

**Neden ayri bir betik:** admin olusturmanin tek yolu admin panelinden
gecmek, panele girmenin tek yolu da admin olmak. Kayit ucunda
`is_admin` bilincli olarak yok -- olsaydi herkes kendini admin
yapardi. Yani bos bir veritabaninda panele hic kimse giremiyordu;
ilk admini acmanin yolu elle SQL yazmakti.

Betik surecin icinden degil, sunucuya erisimi olan birinin elinden
calisiyor: HTTP yuzeyine yeni bir sey acmiyor.

Kullanici zaten varsa yeniden olusturulmuyor, yalnizca admin degilse
admin yapiliyor -- **parolasi degismiyor.** Yetkilendirme parola
sifirlama degil; ezseydi bir hesabi admin yapmak o hesaba girmenin
yolu olurdu. Ayni degerlerle ikinci kez calistirmak guvenli, bu
yuzden kurulum betiklerine ve CI adimlarina konabiliyor.

Kullanici adi ve parola uygulamanin kendi kurallarindan geciyor;
e-posta da oyle. (`example.test` gibi ayrilmis bir alan adi kabul
edilseydi kayit acilir, sonra `/users/` ucu yaniti serilestiremeyip
500 donerdi -- olcup gorduk.)

### Uretime alirken

`ENVIRONMENT=production` iken iki liste **zorunlu**:

```bash
ALLOWED_ORIGINS=["https://linkyoself.com"]   # tarayicidan hangi origin'ler
ALLOWED_HOSTS=["api.linkyoself.com"]         # hangi Host basliklari
```

Bos birakilirsa uygulama ayaga kalkmiyor ve hata neyin eksik oldugunu
soyluyor. **Neden acikca durduruluyor:** eskiden bos liste sessizce
"her origin kabul" anlamina geliyordu. Kod `allowed_origins or ["*"]`
diyordu ve hemen altinda `allow_credentials=True` duruyordu; Starlette
bu ikisini birlikte gorunce yanita `*` yazmiyor, **istegin origin'ini
yansitiyor**. Calisan sunucuda olculdu:

```
$ curl -i -X OPTIONS .../api/v1/profile/me -H "Origin: https://kotu-site.example" ...
access-control-allow-origin: https://kotu-site.example
access-control-allow-credentials: true
```

`ALLOWED_ORIGINS` yazmayi unutan bir dagitim, hicbir uyari cikmadan
her siteye acik hale geliyordu. Sessizce acik olmaktansa acikca
baslamamak tercih edildi.

Gelistirmede `ALLOWED_ORIGINS` bos birakilabilir; o zaman yalnizca
`FRONTEND_URL` kabul edilir. Hicbir ortamda `*` kullanilmiyor --
`allow_credentials=True` ile bir arada zaten bir sey kisitlamiyor.

## Hiz siniri

Sinir eklenmeden once **olculdu**; hicbir uc korunmuyordu:

| Uc | Olcum |
|---|---|
| `POST /v1/auth/token` | 30 yanlis sifre -> 30x401, tek bir 429 yok. Ardisik 3.1 deneme/sn, yani saatte ~11.000 |
| `POST /v1/auth/forgot-password` | 20 istek -> **20 e-posta**, hepsi ayni adrese |
| `POST /v1/auth/register` | 15 deneme -> 15 hesap |

Ayni saldirilar sinirdan sonra (calisan sunucuda):

| Uc | Sonuc |
|---|---|
| Giris, 30 deneme | 10x401, **20x429** |
| Sifirlama, 20 istek | 3x204, 17x429 -> **3 e-posta** |
| Kayit, 15 deneme | **4 hesap**, 11 reddedildi |

### Iki katman

IP **ve** hesap ayri ayri sayiliyor; biri digerinin yerini tutmuyor.
IP katmani dagitik olmayan denemeyi ve kayit spam'ini durduruyor
(kayitta henuz bir hesap yok, sinirlanacak baska anahtar da yok).
Hesap katmani ise tek bir hesaba yonelen denemeyi, saldirgan IP
degistirse bile durduruyor.

Sinirlar ve her birinin gerekcesi: `core/rate_limit/kurallar.py`.

### Girişte yalnizca BASARISIZ denemeler sayiliyor

Uc once bakiyor, sonra yalnizca kimlik dogrulama dustuyse
isaretliyor. Her istegi saysaydik dogru sifreyle giren kullanici da
kendi limitini yakar, sik giris yapan biri kendini disari
kilitleyebilirdi.

### Bilinen bedel: hedefli kilitleme

Hesap bazli her sinir, baskasinin adresini bilen birinin bilerek
yanlis sifre girip o kullaniciyi disari kilitlemesine kapi aciyor.
Kacinmanin yolu sinirsiz birakmak olurdu ki daha kotu. Bedeli ucu
birden kucultuyor: pencere kisa (15 dk), esik gunluk kullanimda
gorulmeyecek kadar yuksek (10), ve asil yuk IP katmaninda.

### X-Forwarded-For koru korune okunmuyor

Basligi istemci uydurabilir; her istekte rastgele bir deger yazan biri
ona guvenen bir sinirlayiciyi tamamen atlatir -- yani sinir tiyatroya
doner. `TRUSTED_PROXY_COUNT` kac tane **guvenilir** ters vekil
oldugunu soyluyor:

- `0` (varsayilan): baslik hic okunmuyor, baglantinin kendi adresi
  kullaniliyor. Vekil arkasinda degilken dogrusu bu.
- `N > 0`: X-Forwarded-For'un **sagdan N.** elemani aliniyor. Vekiller
  gordukleri adresi saga ekliyor, yani saldirganin yazabildigi kisim
  solda kaliyor.

Uygulama bir ters vekil arkasindaysa bu deger **ayarlanmali**, yoksa
butun istekler vekilin tek adresinden geliyor gorunur ve tum
kullanicilar ayni sayaci paylasir.

### IP saklanmiyor

Sayac anahtari IP'nin **SHA-256 ozeti** ve yalnizca surec ici bellekte,
pencere suresince tutuluyor. Ham adres veritabanina da log'a da
yazilmiyor. Bu, gizlilik politikasindaki "IP adresi saklanmiyor"
ifadesiyle uyumlu; politika ayrica kotuye kullanimi engellemek icin
adresin **gecici olarak islendigini** soyluyor.

### Sinirlar SUREC BASINA

Sayaclar surec ici bellekte (bu yiginda Redis yok ve yalnizca bunun
icin isletilecek ikinci bir servis eklemek istenmedi). Uygulama N isci
ile kosarsa gercek sinir N katina cikar, surec yeniden baslayinca
sayaclar sifirlanir. Sinirsiz olmaktan cok daha iyi ama Redis'li bir
cozumle ayni sey degil; kalici bir sinir gerektiginde
`core/rate_limit/limiter.py` yerine paylasilan bir depo konmali.

## Tiklama tekillestirme

OLCULDU: tekillestirme yokken tek bir ziyaretcinin ~2 saniyede yaptigi
10 istek **10 tiklama** olarak sayiliyordu. Cift tiklama, sabirsiz
tekrar dokunuslar ve geri gelip yeniden tiklama, sahibinin gordugu
sayiyi oldugundan buyuk gosteriyordu.

Ayni ziyaretcinin ayni linke tiklamasi `CLICK_DEDUP_SECONDS` (varsayilan
30) icinde **tek** sayiliyor. Ayni olcum tekillestirmeden sonra: 10
istek -> sayac **+1**, ve on yanitin hepsi 200 + `redirect_url`.

### Yanit degismiyor, yalnizca SAYI

Tekrarlanan tiklama da 200 ve hedef adresi aliyor. 429 ya da hata
dondurmek, olcumu duzeltmek icin ziyaretcinin linke gitmesini
engellemek olurdu.

Sayac ve olay **birlikte** atlaniyor: pano toplami sayactan, "son N
gun" grafigi olaylardan okuyor; yalnizca biri tekillestirilseydi iki
ekran farkli sayi gosterirdi.

### Neden 30 saniye

Pencerenin **kapsamasi** gerekenler: cift tiklama (tarayici esigi
~500 ms), sabirsiz tekrar dokunuslar (2-5 sn), geri gelip yeniden
tiklama.

Pencerenin **yutmamasi** gerekenler -- asil kisit bu: anahtar IP, yani
ziyaretci kimligi yok. Ayni adresin arkasinda (okul, ofis, mobil
operatorun CGNAT'i) bircok gercek kisi olabilir. Pencere uzadikca ayni
linke tiklayan FARKLI kisiler tek kisi sayilmaya baslar; 30 dakikalik
bir "oturum" penceresi (Google Analytics varsayilani) onlarca gercek
tiklamayi tek tiklamaya indirirdi.

Bu metrigin isi "kac FARKLI KISI tikladi" degil, "linke ne kadar trafik
gitti" -- yani hedef tekil ziyaretci saymak degil, **kazalari
temizlemek**. Uzun pencere baska bir metrik olurdu ve adi yanlis
olurdu.

### Kotuye kullanim onlemi DEGIL

30 saniyelik pencere, sayiyi bilerek sisirmek isteyen birini dakikada 2
tiklamada tutuyor -- gunde ~2.880. Sayiyi **kazalardan** koruyor,
kasittan degil. Kasit ayri bir is (tiklama ucunun kendisine hiz siniri)
ve bu surumde yok.

### Mekanizma hiz siniriyla ortak

"Pencerede en fazla 1" demek, limit=1 olan bir hiz kurali demek; ayni
sayac kullaniliyor (`core/rate_limit/limiter.py`). Dolayisiyla ayni
sinirlar gecerli: sayaclar **surec ici** bellekte, yani N isci ile
kosulursa tekillestirme de isci basina calisir.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

Testler SQLite (aiosqlite) uzerinde calisir, ayri bir veritabani kurulumu
gerektirmez. Her test sifirdan olusturulan bos bir semada calisir.

**Ayni anda iki pytest kosturmayin.** Veritabani `/tmp` altinda sabit bir
dosya (`tests/conftest.py`), dolayisiyla paralel iki kosu birbirinin
semasini siler ve ikisi de anlamsiz hatalar verir. Tek kosu temizdir.

### Kapsam

```bash
pytest --cov          # rapor + esik denetimi
```

Su an **%91** (2433 ifade, 218'i kapsanmamis). Ayarlar `.coveragerc`'de.

Rakam iki sey sayilmadigi icin bu: testlerin kendisi ve `alembic/`.
Testler dahil edilseydi %95 cikardi -- kendi test dosyalarini sayan bir
kapsam rakami, uygulama kodunun durumunu degil test dosyalarinin
kendi kendini calistirdigini olcer. Migration'lar ise gercek bir
veritabanina karsi calisiyor, birim suitinde degil; olcmek yuzlerce
hic yurutulmeyen satirla sayiyi anlamsizlastirirdi.

`fail_under = 90` bir **mandal**: hedef bir sayiya ulasmak degil,
geriye gitmemek. Bugunku degerin bir puan altinda -- kucuk bir yeniden
duzenleme derlemeyi kirmiyor, gercek bir gerileme yakalaniyor. Kapsam
yukseldikce esik de yukseltilmeli, yoksa mandal gevser.

Olcum **CI adiminda**, `pytest.ini`'deki `addopts`'ta degil. Addopts'a
konsaydi her yerel `pytest` cagrisi -- tek bir dosyayi kosturmak
dahil -- bedeli oderdi (olculdu: 211 -> 224 saniye) ve o tek dosyanin
urettigi yaniltici bir rapor basardi.

### Commit oncesi kanca

```bash
git config core.hooksPath scripts/hooks
```

Bir kez kurulur; `scripts/hooks/pre-commit` commit'ten once
`ruff check .` ve `ruff format --check .` kosturur, gecmezse commit'i
durdurur. Komutlar CI'in kosturdugunun AYNISI, dolayisiyla kanca
gecerse Ruff Check is akisinin da gececegi garanti. Ikisi birlikte
degistirilmeli.

Kanca **pytest kosturmuyor**: paket ~3.5 dakika suruyor ve her
commit'te beklemek kancayi atlatilan bir seye cevirirdi. Testleri CI
kosuyor.

### Bicimlendirme

Depo `ruff format` ile bicimlendirilmis. Bir donem degildi: 79
dosyanin 57'si gecmiyordu ve o yuzden ne kancada ne CI'da format
denetimi vardi -- eklemek, ilgisiz 57 dosyayi bicimlendirmeden once
her commit'i durdururdu. Bicimlendirme tek seferde yapildi ve denetim
**ayni anda hem kancaya hem CI'a** eklendi. Yalnizca birine eklemek
ise yaramazdi: kanca opt-in, yani kurmamis biri bozuk format push
edebilir; CI'siz de bir seferlik temizlik zamanla yine dagilirdi.

Satir uzunlugu ayarlanmadi, ruff'in varsayilani (88) kullaniliyor.
Olculdu: 11954 satirin yalnizca 128'i 88 karakteri geciyordu ve en
uzun satir 111'di, yani depo zaten bu genislige yakin yazilmisti.

Denetim **duzeltmiyor, yalnizca durduruyor**. Kanca dosyalari
kendiliginden degistirseydi commit edilen sey gelistiricinin gordugu
sey olmazdi: `git add` edilmis icerikle commit'e giden icerik
ayrisirdi.

**Migration'lar bicimlendirme denetiminin disinda** (`ruff.toml`,
`[format] exclude`). Onlari insan yazmiyor, `alembic revision
--autogenerate` uretiyor ve cikti bu bicimde gelmiyor; denetim
kapsasaydi her yeni migration'dan sonra kanca duser, gelistirici de
anlamsiz bir `ruff format .` adimi atmak zorunda kalirdi.

Bu **yalnizca bicimlendirme**. `exclude`'u ust seviyeye koymak
`ruff check`i de kapsardi ve migration'lar lint edilmez olurdu; o
yuzden `[format]` bolumunde. Olculdu: migration'lardaki kullanilmayan
bir import `ruff check`te hala F401 veriyor, bozuk bicim ise
`ruff format --check`te gorunmuyor.

### CI

`.github/workflows/tests.yml` (pytest) ve `ruff.yml` (lint) `pull_request`
ile, `push`ta ise yalnizca `dev` ve `main` icin kosar. `on: [push,
pull_request]` iken acik PR'i olan bir dala push yapmak ayni commit icin
her isi iki kez kosturuyordu. Ayni daldaki eski kosu, yenisi gelince
iptal ediliyor.

## Sifre sifirlama

`POST /auth/forgot-password` tek kullanimlik bir token uretip kullaniciya
e-posta ile `FRONTEND_URL/password-change?token=...` baglantisini gonderir.

- Token'in veritabaninda yalnizca SHA-256 ozeti saklanir.
- E-posta kayitli olmasa bile uc 204 doner; farkli yanit vermek bir adresin
  sistemde olup olmadigini ogrenmeye yarardi.
- Yeni talep, bekleyen eski token'lari gecersiz kilar.
- Sifre degisince kullanicinin tum refresh token'lari da iptal edilir.

`SMTP_HOST` bos birakilirsa e-posta gonderilmez, icerigi log'a yazilir; akis
bir SMTP saglayicisi secilmeden de uctan uca calisir.

## Mimari

```
routers/          HTTP katmani (routers/v1/* surumlenmis endpoint'ler)
services/         Is kurallari + DTO'lar (Pydantic)
repositories/     Veri erisimi (SQLAlchemy async)
core/             Ortak altyapi: auth, exception'lar, response zarfi
di/container.py   dependency-injector container'i
models.py         SQLAlchemy modelleri
alembic/          Migration'lar
```

Tum yanitlar ortak bir zarf kullanir:

```json
{ "status": "success", "message": "...", "data": { } }
```

## Endpoint'ler

Tum yollar `/api/v1` onekiyle servis edilir.

### Auth
| Method | Yol | Aciklama |
|---|---|---|
| POST | `/auth/register` | Kayit (username, email, password) |
| POST | `/auth/token` | Giris — `username` alanina e-posta veya kullanici adi |
| POST | `/auth/refresh` | Refresh token ile yeni access token |
| POST | `/auth/logout` | Kullanicinin tum refresh token'larini iptal eder |
| POST | `/auth/forgot-password` | Sifirlama baglantisi gonderir (her zaman 204) |
| POST | `/auth/reset-password` | Token ile yeni sifreyi kaydeder |

### Kullanici
| Method | Yol | Aciklama |
|---|---|---|
| GET | `/users/me` | Giris yapmis kullanici |
| GET | `/users/{user_id}` | Id ile kullanici |
| GET | `/users/` | Tum kullanicilar (`is_admin` gerekir) |

### Profil & onboarding
| Method | Yol | Aciklama |
|---|---|---|
| GET | `/profile/me` | Profil detayi |
| GET | `/profile/onboarding-status` | Hangi adimda oldugu |
| POST | `/profile/complete-step-1..4` | Onboarding adimlari |
| PUT | `/profile/update` | Profili topluca guncelle |
| POST | `/profile/complete-onboarding` | Onboarding'i tamamla |
| POST | `/profile/skip-onboarding` | Onboarding'i atla |

### Linkler
| Method | Yol | Aciklama |
|---|---|---|
| POST | `/links/` | Link olustur |
| GET | `/links/` | Linkleri listele (`?include_inactive=true`) |
| GET/PUT/DELETE | `/links/{link_id}` | Link detay / guncelle / sil |
| POST | `/links/reorder` | Siralamayi degistir |
| PATCH | `/links/{link_id}/toggle` | Aktif/pasif |
| POST | `/links/{link_id}/click` | **Public** — tiklanmayi kaydeder |

Tiklama ucunun govdesi opsiyonel: `{"referrer": "<tam URL>"}` verilirse
ziyaretcinin bu sayfaya hangi siteden geldigi kaydedilir. Istegin kendi
`Referer` basligi bunun yerine gecemez — o her zaman kendi profil
sayfamizi gosterir (bkz. `utils/referrer.py`). Sunucu yalnizca host'u
saklar; yol ve sorgu kismi atilir.

### Analytics
| Method | Yol | Aciklama |
|---|---|---|
| GET | `/analytics/summary` | Tum zamanlarin toplamlari |
| GET | `/analytics/timeseries` | Gunluk tiklama + profil goruntulenme |
| GET | `/analytics/timeseries/by-link` | Ayni aralik, link kirilimiyla |
| GET | `/analytics/referrers` | Tiklamalarin kaynak dagilimi |
| GET | `/analytics/best-times` | Tiklamalarin haftaguno ve saate dagilimi (`?tz=Europe/Istanbul`) |

**Aralik.** Bu dort uc araligi iki sekilde aliyor:

- `?days=1..90` — son N gun (bugun dahil). Varsayilan 7, `best-times`
  icin 30.
- `?start=YYYY-AA-GG&end=YYYY-AA-GG` — belirli bir aralik, iki ucu da
  dahil, UTC gunlerine gore. Verilirse `days` yok sayilir.

Ikisi birlikte verilmeli; tek basina `start` ya da `end` 422 doner
("start'tan bugune" mi, "start'tan days gun" mu belirsiz). `start > end`
ve `MAX_DAYS`i (90) asan aralik da 422.

`end` gelecekte olabilir; o gunler bos doner. Kirpmak, kullanicinin
istedigi araligi sessizce degistirmek olurdu.

Zaman serisi uclari `analytics_events` tablosunu okuyor; toplamlar ise
sayaclardan geliyor. Olay kaydi sonradan eklendigi icin bu iki grubun
sayilari birbirini tutmayabilir.

`/analytics/best-times` saat dilimini istekten aliyor: olaylar UTC
saklaniyor ve "en cok tiklama saat 14'te" bilgisi kullanicinin kendi
saatine cevrilmeden bir sey anlatmiyor. Cevrim sunucuda, `zoneinfo` ile
yapiliyor; yaz saati gecisleri de dogru. Yanittaki `enough_data` false
iken `peak_weekday` / `peak_hour` bir cikarim degil, yalnizca en buyuk
kutunun adi.

### Public profil
| Method | Yol | Aciklama |
|---|---|---|
| GET | `/p/{username}` | **Public** — profil + aktif linkler (`count_view=false` ile sayilmadan) |
| GET | `/p/sitemap/profiles` | **Public** — sitemap icin profil listesi |
| GET | `/p/sitemap/count` | **Public** — o listenin uzunlugu |

`/p/{username}` token gerektirmez, buyuk/kucuk harf duyarsizdir ve
e-posta / id / admin gibi hassas alanlari donmez.

**`count_view=false` ile sayimsiz okunur.** Bu cagri varsayilan olarak
bir "profil goruntulenmesi" sayiliyor: hem `profile_view_count` hem de
zaman serisindeki olay kaydi artiyor. Ama ayni ucu sayfa disinda
cagiran yerler de var -- frontend paylasim kartini (`opengraph-image`)
cizerken profili yeniden okuyor. Bayraksiz halde bir kaziyicinin kart
istegi ziyaret olarak sayiliyor, yani kimsenin gormedigi bir sayfa
goruntulenme uretiyordu. Bayrak yalnizca sayimi kapatiyor; donen
profil birebir ayni.

Kotuye kullanim tarafinda bir sey acmiyor: bayrak sayiyi yalnizca
*azaltabiliyor*, sisirmenin yolu degil -- sayac zaten hic istek
atmamakla da artmiyor.

`/p/sitemap/profiles` frontend'in `sitemap.xml`'i uretmesi icin var:
her satirda yalnizca `username` ve `last_modified`.

**En az bir gorunur linki olan profiller doner.** Sitemap arama
motoruna "sitenin onemli sayfalari bunlar" demek; kayit olup hicbir
sey eklememis bir hesabin bos sayfasi oraya girerse hem ziyaretciyi
hem de sitenin genel degerlendirmesini asagi ceker.

`last_modified` profilin ve linklerinin en yeni degisiklik tarihi --
yalnizca `User.updated_at`'e bakmak link eklenmesini kacirirdi.

`limit` (varsayilan 1000, en fazla 5000) ve `offset` ile sayfalanir;
`limit`ten az satir donmesi listenin bittigini gosterir. Yol iki
segmentli: tek segmentli olsaydi `sitemap` adli bir kullanicinin
profilini golgelerdi.

`/p/sitemap/count` ayni kosulla sayiyor. Frontend sitemap'i 50.000
URL'lik standart sinirin altinda tutmak icin parcalara boluyor ve kac
parca gerektigini buradan ogreniyor; listeyi bastan sona okuyup saymak
her parca icin butun listeyi cekmek demekti.

**Kosul iki sorguda da ayni fonksiyondan geliyor.** Ayrisirlarsa parca
sayisi liste uzunluguyla tutmaz -- son parca eksik kalir ya da bos bir
parca uretilir -- ve bu yalnizca profil sayisi belirli bir esige
gelince ortaya cikar.
