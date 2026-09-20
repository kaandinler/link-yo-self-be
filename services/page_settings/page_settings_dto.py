"""Sayfa ayarlarinin istek/yanit semalari."""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# extra_settings'in JSON'a cevrildikten sonraki en buyuk boyutu.
# NEDEN SINIR VAR: alanin semasi yok, yani istemci ne koyarsa o
# saklaniyor. Sinirsiz birakmak tek bir istekle satiri megabaytlarca
# sisirmeye izin verirdi.
EXTRA_SETTINGS_MAX_BAYT = 4096


class PageSettingsUpdate(BaseModel):
    """Kismi guncelleme; verilmeyen alan degismiyor.

    KAPSAM: burada yalnizca users tablosunda karsiligi OLMAYAN ayarlar
    var. Arka plan, tema rengi ve profil fotografi PUT /profile/update
    ile yonetiliyor; ikisini de buradan kabul etmek ayni gorunumu iki
    ayri uctan degistirilebilir yapardi.
    """

    adult_warning_enabled: bool | None = None
    extra_settings: dict[str, Any] | None = Field(
        None,
        description="Semasi olmayan ek ayarlar; yalnizca sahibine donuyor.",
    )

    @field_validator("adult_warning_enabled")
    @classmethod
    def acikca_null_olamaz(cls, deger: bool | None) -> bool:
        """Acikca gonderilen null 422 veriyor.

        Kolon nullable=False; None yazilsaydi IntegrityError patlar ve
        istemci 500 gorurdu. Alanin HIC gonderilmemesi ayri bir durum ve
        serbest: dogrulayici varsayilan icin calismiyor, yalnizca deger
        gercekten verildiginde.
        """
        if deger is None:
            raise ValueError("adult_warning_enabled cannot be null")
        return deger

    @field_validator("extra_settings")
    @classmethod
    def boyutu_dogrula(cls, deger: dict | None) -> dict | None:
        if deger is None:
            return deger

        # Anahtar sayisi degil, JSON boyutu olculuyor: tek anahtarin
        # altinda cok buyuk bir metin de olabilir.
        boyut = len(json.dumps(deger).encode("utf-8"))
        if boyut > EXTRA_SETTINGS_MAX_BAYT:
            raise ValueError(
                f"extra_settings too large: {boyut} bytes "
                f"(max {EXTRA_SETTINGS_MAX_BAYT})"
            )

        return deger


class PageSettingsRead(BaseModel):
    """Sahibine donen ayarlar.

    user_id de doniyor ki istemci yanitin kime ait oldugunu
    dogrulayabilsin; extra_settings yalnizca bu ucta, herkese acik
    profilde yok.
    """

    user_id: int
    adult_warning_enabled: bool = False
    extra_settings: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)
