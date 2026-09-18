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
