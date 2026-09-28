"""db.py: oturum fabrikasi ve islem sinirlari.

Kapsamda eksik kalan satirlar hata yollariydi: fabrika kurulmadan
cagrilma ve bir islem ortasinda hata olunca GERI ALMA. Ikincisi en az
gozlemlenen ama en cok guvenilen davranis: repository'lerin yazma
islemlerinin tamami run_in_transaction'dan geciyor (create, update,
delete, update_link_orders). Geri alma calismasaydi, ortasinda hata
alan bir islem yarim yazilmis veri birakirdi.
"""

import pytest
from sqlalchemy import func, select

import db
from models import Link
from tests.conftest import register_user


async def _link_sayisi() -> int:
    async def say(session):
        return (await session.execute(select(func.count(Link.id)))).scalar()

    return await db.execute_without_transaction(say)


def _link(user_id: int, baslik: str) -> Link:
    return Link(
        user_id=user_id,
        title=baslik,
        url="https://ornek.test",
        order_index=1,
        border_radius=8,
    )


class TestIslemSinirlari:
    async def test_basarili_islem_kalici(self, client):
        kullanici = await register_user(client)

        async def ekle(session):
            session.add(_link(kullanici["id"], "kalici"))
            await session.flush()
            return "tamam"

        assert await db.run_in_transaction(ekle) == "tamam"
        assert await _link_sayisi() == 1

    async def test_hata_olunca_yarim_yazim_geri_aliniyor(self, client):
        """Iki satir yazilip ucuncu adimda hata: HICBIRI kalmamali."""
        kullanici = await register_user(client)

        async def yarida_kalan(session):
            session.add(_link(kullanici["id"], "bir"))
            session.add(_link(kullanici["id"], "iki"))
            # Satirlar veritabanina gitti ama islem henuz bitmedi.
            await session.flush()
            raise RuntimeError("ucuncu adimda hata")

        with pytest.raises(RuntimeError, match="ucuncu adimda hata"):
            await db.run_in_transaction(yarida_kalan)

        assert await _link_sayisi() == 0

    async def test_hata_cagirana_ulasiyor(self, client):
        """Geri alma hatayi yutmamali; yutsaydi ust katman "basarili"
        sanip 200 donerdi."""

        async def patla(session):
            raise ValueError("ozgun hata")

        with pytest.raises(ValueError, match="ozgun hata"):
            await db.run_in_transaction(patla)


class TestFabrika:
    def test_kurulmadan_cagrilirsa_acik_hata(self, monkeypatch):
        """Fabrika kurulmamissa None ile devam edip anlamsiz bir
        AttributeError vermek yerine neyin eksik oldugunu soylemeli."""
        monkeypatch.setattr(db, "_session_factory", None)

        with pytest.raises(RuntimeError, match="Session factory not initialized"):
            db.get_session_factory()
