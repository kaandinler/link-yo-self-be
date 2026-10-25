# Agent sistemi

Iki Claude Code subagent'i, mevcut is akisini (dal -> PR -> `dev` -> `main`)
otomatiklestiriyor. Yeni bir akis icat etmiyor.

| Agent | Dosya | Isi | Yapamadigi |
|---|---|---|---|
| `pm` | `.claude/agents/pm.md` | ROADMAP + PR'lar + CI'a bakip siradaki TEK isi secer, task tanimi yazar | Kod yazmak, PR acmak |
| `ship` | `.claude/agents/ship.md` | Task'i alir, dal acar, kod + test yazar, yesile getirir, PR acar | `main`, deploy, SSH, secret |

Kurallarin teknik bariyeri `.claude/settings.json`: `main`'e push, force push,
SSH/SCP, workflow tetikleme, PR merge ve `.env` okuma/yazma reddediliyor.
Agent bir kurali unutsa bile yapamiyor.

## Iki depo birlikte

Agent'lar BE deposundan calistiriliyor; FE deposu kardes dizinde olmali
(docker-compose zaten bunu bekliyor):

```
calisma-dizini/
  link-yo-self-be/   <- claude burada calisir
  link-yo-self-fe/
```

FE'ye dokunan bir task'ta ship agent'i `../link-yo-self-fe` icinde dal acip
oradan PR aciyor. FE deposunun da kendi `CLAUDE.md`'si var.

## Elle calistirma

```bash
cd link-yo-self-be
claude "pm agent'ini calistir, sonra cikan task'i ship agent'ina ver"
```

Yalnizca plan gormek icin: `claude "pm agent'ini calistir, task'i yaz ama uygulama"`.

## Zamanlanmis calistirma

Gunde bir iki kez tetiklenen bir zamanlanmis gorev icin prompt:

> link-yo-self-be ve kardes dizindeki link-yo-self-fe depolarinda calis.
> Once `pm` subagent'ini calistir ve siradaki tek task'i sectir. Sonra o
> task'i `ship` subagent'ina ver. En fazla bir PR ac. `docs/ROADMAP.md`'deki
> "Kaan'in karari bekleniyor" maddelerine dokunma. Sonunda ne yapildigini
> ve PR linkini tek paragrafta ozetle.

Abonelik limitleri gercek bir sinir: her calisma bir task, gunde 1-2 calisma
makul bir baslangic.

## Her zaman insanda kalanlar

- PR'lari `dev`'e ve `dev`'i `main`'e merge etmek
- Deploy workflow'unu tetiklemek ve onaylamak
- Para harcanan her sey: domain, sunucu, SMTP
- Guvenlik ayarlarinda gevsetme
- Urun yonu
