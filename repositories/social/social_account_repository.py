# repositories/social/social_account_repository.py


from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import Platform, SocialAccount


class SocialAccountRepository(BaseRepository[SocialAccount]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = SocialAccount

    async def get_by_user(self, user_id: int) -> list[SocialAccount]:
        """Kullanicinin sosyal hesaplari, id sirasiyla.

        Siralama alani yok (links'teki order_index'in karsiligi burada
        bulunmuyor), bu yuzden ekleme sirasi = id sirasi kullaniliyor.
        Sirasiz donmek listeyi her istekte farkli dizebilirdi.
        """

        async def _get_by_user(
            session: AsyncSession, user_id_: int
        ) -> list[SocialAccount]:
            query = (
                select(SocialAccount)
                .where(
                    and_(
                        SocialAccount.user_id == user_id_,
                        SocialAccount.is_deleted.is_(False),
                    )
                )
                .order_by(SocialAccount.id.asc())
            )

            result = await session.execute(query)
            return result.scalars().all()

        return await self.execute_query(_get_by_user, user_id, transactional=False)

    async def get_duplicate(
        self,
        user_id: int,
        platform_id: int,
        username: str,
        haric_tut_id: int | None = None,
    ) -> SocialAccount | None:
        """Tekillik kisitini ihlal edecek kaydi arar.

        NEDEN ONCEDEN BAKILIYOR: veritabaninda
        uq_user_platform_username kisiti var ve ihlali IntegrityError
        olarak patlar -- istemciye 500 doner. Buradan bakinca ayni durum
        409 oluyor.

        `haric_tut_id` guncelleme icin: kaydin kendisi kendisiyle
        cakisiyor sayilmamali, aksi halde bir hesap hicbir alani
        degismeden guncellenemezdi.
        """

        async def _get_duplicate(
            session: AsyncSession,
            user_id_: int,
            platform_id_: int,
            username_: str,
            haric_: int | None,
        ) -> SocialAccount | None:
            kosullar = [
                SocialAccount.user_id == user_id_,
                SocialAccount.platform_id == platform_id_,
                SocialAccount.username == username_,
                SocialAccount.is_deleted.is_(False),
            ]
            if haric_ is not None:
                kosullar.append(SocialAccount.id != haric_)

            result = await session.execute(select(SocialAccount).where(and_(*kosullar)))
            return result.scalars().first()

        return await self.execute_query(
            _get_duplicate,
            user_id,
            platform_id,
            username,
            haric_tut_id,
            transactional=False,
        )

    async def list_platforms(self) -> list[Platform]:
        """Secilebilir platformlar, ada gore sirali."""

        async def _list_platforms(session: AsyncSession) -> list[Platform]:
            result = await session.execute(
                select(Platform)
                .where(Platform.is_deleted.is_(False))
                .order_by(Platform.name.asc())
            )
            return result.scalars().all()

        return await self.execute_query(_list_platforms, transactional=False)

    async def get_platform(self, platform_id: int) -> Platform | None:
        """Tek platform; olmayan bir id ile hesap acilmasini engellemek icin."""

        async def _get_platform(
            session: AsyncSession, platform_id_: int
        ) -> Platform | None:
            result = await session.execute(
                select(Platform).where(
                    and_(
                        Platform.id == platform_id_,
                        Platform.is_deleted.is_(False),
                    )
                )
            )
            return result.scalars().first()

        return await self.execute_query(_get_platform, platform_id, transactional=False)

    # --- Platform yonetimi (admin) ---------------------------------------

    async def list_platforms_all(self) -> list[Platform]:
        """Emekliye ayrilmislar DAHIL butun platformlar.

        Yonetim ekrani icin: emekli bir platformu geri getirmek
        isteyen birinin once onu gorebilmesi gerekiyor.
        """

        async def _list_all(session: AsyncSession) -> list[Platform]:
            result = await session.execute(select(Platform).order_by(Platform.name))
            return result.scalars().all()

        return await self.execute_query(_list_all, transactional=False)

    async def get_platform_by_name(self, name: str) -> Platform | None:
        """Ada gore platform; SILINMISLER DE DAHIL.

        NEDEN SILINMISLER DE: `name` kolonu UNIQUE. Emekliye ayrilmis
        bir platformun adiyla yenisini INSERT etmek IntegrityError ile
        patlar ve istemci 500 gorur. Buradan bakinca ayni durum
        "eskisini geri getir"e donusuyor (bkz. service.create_platform).
        """

        async def _get_by_name(session: AsyncSession, name_: str) -> Platform | None:
            result = await session.execute(
                select(Platform).where(Platform.name == name_)
            )
            return result.scalars().first()

        return await self.execute_query(_get_by_name, name, transactional=False)

    async def get_platform_any(self, platform_id: int) -> Platform | None:
        """Id'ye gore platform; silinmisler de dahil."""

        async def _get_any(session: AsyncSession, id_: int) -> Platform | None:
            result = await session.execute(select(Platform).where(Platform.id == id_))
            return result.scalars().first()

        return await self.execute_query(_get_any, platform_id, transactional=False)

    async def create_platform(self, platform: Platform) -> Platform:
        return await self.create(platform)

    async def update_platform(self, platform: Platform) -> Platform:
        return await self.update(platform)

    async def count_accounts_for_platform(self, platform_id: int) -> int:
        """Bu platformda kac sosyal hesap var.

        Silme ekranindaki uyari icin: yonetici, emekliye ayirmanin kac
        kullaniciyi etkileyecegini gormeden karar vermemeli.
        """

        async def _say(session: AsyncSession, id_: int) -> int:
            result = await session.execute(
                select(func.count())
                .select_from(SocialAccount)
                .where(
                    and_(
                        SocialAccount.platform_id == id_,
                        SocialAccount.is_deleted.is_(False),
                    )
                )
            )
            return int(result.scalar_one())

        return await self.execute_query(_say, platform_id, transactional=False)
