# LinkYoSelf — backend (CLAUDE.md)

Linktree benzeri "link in bio" servisinin FastAPI backend'i. Frontend ayri
depoda: `link-yo-self-fe` (Next.js). Iki depo yan yana duruyor; butun yigin
bu depodaki `docker-compose.yml` ile kalkiyor.

Kurulum, ortam degiskenleri, uretim notlari ve her tasarim kararinin
gerekcesi `README.md`'de. Burada tekrar edilmiyor -- once oraya bak.

## Komutlar

```bash
pip install -r requirements-dev.txt
pytest -q                 # butun suit (SQLite, Redis yoksa Redis testleri atlanir)
pytest --cov -q           # CI'daki gibi, kapsam esigiyle (.coveragerc)
ruff check . && ruff format --check .
alembic upgrade head      # yerel Postgres'e karsi
docker compose up --build # butun yigin (kardes dizinde FE gerekli)
```

## Yonetim

- Is listesi: `docs/ROADMAP.md`. Agent sistemi: `docs/AGENTS.md`.
- Subagent'lar: `.claude/agents/pm.md` (siradaki isi secer), `.claude/agents/ship.md` (isi bitirip PR acar).

## Dal, commit, PR

- Akis: `claude/<kisa-ad>` dali -> PR -> `dev` -> (insan) `main`.
- Commit mesajlari Turkce, ASCII (s/c/g/i/o/u), conventional prefix:
  `feat(kapsam): ...`, `fix(...)`, `ci(...)`, `docs(...)`, `chore(...)`.
- PR aciklamasi: ne, NEDEN, nasil test edildi. Olcum yapildiysa sayisi.
- Bir PR tek bir is. Kapsam buyumez.

## Kod stili

- Katmanlar: `routers/` -> `services/` -> `repositories/`; DI `di/container.py`.
- Yorumlar "ne" degil "NEDEN"i anlatir; README ile ayni ton. Bir karar
  olculduyse olcum yaziliyor.
- Yeni davranis = yeni test. CI'da kapsam esigi bir mandal; dusurulmez.

## KESIN KURALLAR

- `main`'e push yok, force push yok. `main`'e merge insan isi.
- Deploy komutu calistirilmaz, sunucuya SSH/SCP yapilmaz.
- `.env*` (ornek dosyalar haric) okunmaz, yazilmaz; gercek secret hicbir dosyaya yazilmaz.
- Guvenlik ayarlari gevsetilmez: CORS / `ALLOWED_HOSTS` / hiz siniri /
  avatar sinirlari. Bir test bunlarla catisiyorsa test duzeltilir.
- Domain hardcode edilmez; `${DOMAIN}` / ortam degiskeni kullanilir.
