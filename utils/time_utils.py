from datetime import UTC, datetime


def utcnow():
    """Su anki zamani UTC olarak, saat dilimi bilgisiyle birlikte doner.

    NEDEN datetime.utcnow() DEGIL: o, saat dilimi bilgisi OLMAYAN
    (naive) bir deger doner. Naive bir deger, saat dilimli bir degerle
    karsilastirildiginda TypeError veriyor; bu kodda ikisi de ayni
    yerde bulusuyor (ornegin token son kullanma kontrolu). Tek bir
    kaynaktan gecmek, "hangisi naive?" sorusunu tamamen ortadan
    kaldiriyor.
    """
    return datetime.now(UTC)
