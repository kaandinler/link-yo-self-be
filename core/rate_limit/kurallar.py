"""Sinirlar tek yerde.

HER SAYININ BIR GEREKCESI VAR; hicbiri "makul gorundu" diye secilmedi.
Olcum, sinir eklenmeden once yapildi (bkz. limiter.py modul
docstring'i).

TEK BIR ILKE: mesru kullaniciyi gunluk kullanimda hic gormeyecegi bir
esik, saldirganin isini ise anlamli olcude bozacak bir esik. Ikisi
catistiginda mesru kullanici kazaniyor -- disari kilitlenen gercek bir
kullanici, yavaslamis bir saldirgandan daha pahali.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Kural:
    limit: int
    pencere_sn: int


DAKIKA = 60
SAAT = 60 * 60

# --- Giris ---------------------------------------------------------------
#
# Olculdu: sinir yokken ardisik 3.1 deneme/sn, yani saatte ~11.000.
#
# YALNIZCA BASARISIZ DENEMELER SAYILIYOR (bkz. limiter.isaretle), yani
# dogru sifreyle giren kullanici bu sayaclara hic dokunmuyor.
#
# BILINEN BEDEL: hesap basina bir sinir, hedefli bir hizmet engeline
# kapi aciyor -- baskasinin adresini bilen biri bilerek yanlis sifre
# girip o kullaniciyi disari kilitleyebilir. Bu, hesap bazli her
# sinirin dogasinda var; kacinmanin yolu sinirsiz birakmak olurdu ki
# daha kotu. Uc sey bedeli kucultuyor:
#   1. Pencere KISA (15 dk), yani kilit kalici degil.
#   2. Esik, gercek bir kullanicinin gunluk kullanimda gormeyecegi
#      kadar yuksek (10) -- ilk tasarimda 5'ti, kilitlemeyi iki kat
#      ucuzlattigi icin yukseltildi.
#   3. Asil yuk IP katmaninda: tek bir saldirganin yaygin durumunu
#      zaten orasi kesiyor.
#
# IP sinirinin daha GENIS olmasinin sebebi tersi: bir IP'nin arkasinda
# (NAT, ofis, mobil operator) bircok mesru kullanici olabilir; bir
# hesabin arkasinda bir kisi var.
GIRIS_HESAP = Kural(limit=10, pencere_sn=15 * DAKIKA)
GIRIS_IP = Kural(limit=20, pencere_sn=15 * DAKIKA)

# --- Sifre sifirlama -----------------------------------------------------
#
# Olculdu: 20 istek -> 20 e-posta, hepsi ayni adrese. Bedeli yalnizca
# bizim degil: adresin sahibi postayi yiyor, saglayicinin gozunde de
# gonderen itibarimiz dusuyor.
#
# Burada basarili/basarisiz ayrimi YOK: istegin yapilmis olmasi zaten
# bir e-posta demek.
SIFIRLAMA_HESAP = Kural(limit=3, pencere_sn=SAAT)
SIFIRLAMA_IP = Kural(limit=5, pencere_sn=SAAT)

# --- Kayit ---------------------------------------------------------------
#
# Olculdu: 15 deneme -> 15 hesap. Kayitta henuz bir hesap yok, yani
# IP'den baska sinirlanacak bir anahtar da yok.
#
# Saatte 5: bir kisi bir hesap aciyor; ayni agdan bir grup da acsa bu
# esigi gunluk kullanimda gormez.
KAYIT_IP = Kural(limit=5, pencere_sn=SAAT)

# --- Tek kullanimlik token tasiyan uclar ---------------------------------
#
# /reset-password ve /verify-email token'i govdede aliyor. Token'lar
# SHA-256 ozeti olarak saklaniyor ve tahmin edilemez, yani asil risk
# bulunmalari degil; yine de sinirsiz deneme birakmanin bir gerekcesi
# yok ve bu uclar CPU harciyor.
TOKEN_IP = Kural(limit=10, pencere_sn=SAAT)

# --- Dogrulama postasini yeniden gonderme --------------------------------
#
# Giris yapmis kullanici cagiriyor, yani anahtar dogrudan kullanicinin
# kendisi. Yine e-posta uretiyor.
YENIDEN_GONDER_KULLANICI = Kural(limit=3, pencere_sn=SAAT)
