"""Profil ve onboarding akisi testleri."""


class TestProfilePrefix:
    async def test_profil_yolu_tek_prefix_kullanir(self, auth_client):
        """Regresyon: eskiden /api/v1/profile/profile/me seklinde
        cift prefix vardi."""
        assert (await auth_client.get("/api/v1/profile/me")).status_code == 200
        assert (await auth_client.get("/api/v1/profile/profile/me")).status_code == 404


class TestOnboardingStatus:
    async def test_yeni_kullanici_ilk_adimda(self, auth_client):
        response = await auth_client.get("/api/v1/profile/onboarding-status")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["step"] == 1
        assert data["completed_steps"] == []
        assert data["profile_completion_percentage"] == 0
        assert data["can_skip"] is True

    async def test_adim_tamamlaninca_ilerler(self, auth_client):
        await auth_client.post(
            "/api/v1/profile/complete-step-1", json={"display_name": "Kaan"}
        )

        durum = await auth_client.get("/api/v1/profile/onboarding-status")
        data = durum.json()["data"]

        assert 1 in data["completed_steps"]
        assert data["step"] == 2


class TestProfileSteps:
    async def test_adim1_temel_bilgiler(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-1",
            json={"first_name": "Kaan", "last_name": "Dinler", "bio": "Merhaba"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["first_name"] == "Kaan"
        assert data["bio"] == "Merhaba"

    async def test_adim2_website_https_ile_tamamlanir(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-2",
            json={"page_title": "Kaan'in Sayfasi", "website": "kaandinler.dev"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["website"] == "https://kaandinler.dev"

    async def test_adim3_sosyal_medya_at_isareti_temizlenir(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-3",
            json={"twitter_username": "@kaandinler", "instagram_username": "kaan"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["twitter_username"] == "kaandinler"
        assert data["instagram_username"] == "kaan"

    async def test_adim4_tema(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-4",
            json={"theme_color": "#FF5733", "background_type": "gradient"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["theme_color"] == "#FF5733"

    async def test_gecersiz_tema_rengi_422(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-4", json={"theme_color": "kirmizi"}
        )
        assert response.status_code == 422

    async def test_gecersiz_background_type_422(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-4", json={"background_type": "video"}
        )
        assert response.status_code == 422


class TestProfileUpdateNormalizasyon:
    """Regresyon: PUT /profile/update, onboarding adimlarindaki normalizasyonu
    uygulamiyordu. Normalize edilmemis website degeri frontend'de goreli yol
    sayilip linki kiriyordu.
    """

    async def test_website_https_ile_tamamlanir(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update", json={"website": "kaandinler.dev"}
        )

        assert response.status_code == 200
        assert response.json()["data"]["website"] == "https://kaandinler.dev"

    async def test_sosyal_medya_at_isareti_temizlenir(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={
                "twitter_username": "@kaandinler",
                "instagram_username": "  @kaan  ",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["twitter_username"] == "kaandinler"
        assert data["instagram_username"] == "kaan"

    async def test_gecersiz_website_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update", json={"website": "bu bir adres degil"}
        )
        assert response.status_code == 422

    async def test_gecersiz_tema_rengi_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update", json={"theme_color": "kirmizi"}
        )
        assert response.status_code == 422

    async def test_gecersiz_background_type_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update", json={"background_type": "video"}
        )
        assert response.status_code == 422

    async def test_dokunulmayan_alanlar_varsayilana_dusmez(self, auth_client):
        """Adim DTO'larindan farkli olarak burada bos alan varsayilana dusmemeli."""
        await auth_client.put(
            "/api/v1/profile/update", json={"theme_color": "#FF5733"}
        )

        response = await auth_client.put(
            "/api/v1/profile/update", json={"bio": "Merhaba"}
        )

        assert response.status_code == 200
        assert response.json()["data"]["theme_color"] == "#FF5733"


class TestProfileUpdate:
    async def test_profil_guncellenir(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={"display_name": "Kaan D.", "bio": "FastAPI & Flutter"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["display_name"] == "Kaan D."
        assert data["bio"] == "FastAPI & Flutter"

    async def test_tamamlanma_yuzdesi_artar(self, auth_client):
        onceki = (await auth_client.get("/api/v1/profile/me")).json()["data"][
            "profile_completion_percentage"
        ]

        await auth_client.put(
            "/api/v1/profile/update",
            json={"display_name": "Kaan", "bio": "Merhaba", "page_title": "Sayfam"},
        )

        sonraki = (await auth_client.get("/api/v1/profile/me")).json()["data"][
            "profile_completion_percentage"
        ]
        assert sonraki > onceki
        # Kesin deger: yedi alandan ucu dolu.
        assert onceki == 0
        assert sonraki == int(3 / 7 * 100)


class TestOnboardingTamamlama:
    async def test_onboarding_tamamlanir(self, auth_client):
        response = await auth_client.post("/api/v1/profile/complete-onboarding")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["onboarding_completed"] is True
        assert data["profile_completed"] is True

    async def test_onboarding_atlanir(self, auth_client):
        response = await auth_client.post("/api/v1/profile/skip-onboarding")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["onboarding_completed"] is True
        # Atlanan onboarding profili tamamlanmis saymaz
        assert data["profile_completed"] is False


class TestProfileYetkilendirme:
    async def test_tokensiz_erisim_401(self, client):
        for method, path in [
            ("get", "/api/v1/profile/me"),
            ("get", "/api/v1/profile/onboarding-status"),
            ("put", "/api/v1/profile/update"),
            ("post", "/api/v1/profile/complete-onboarding"),
        ]:
            response = await getattr(client, method)(path)
            assert response.status_code == 401, f"{method} {path}"


class TestArkaPlanDegeri:
    """Arka plan degeri tipiyle uyumlu olmali.

    Public profil sayfasi gecersiz degerde varsayilana dusuyordu ama bu
    sessizce oluyordu: kullanici "kaydedildi" mesajini aliyor, sonra
    sayfasinda hicbir sey degismedigini goruyordu.
    """

    async def test_renk_tipinde_hex_kabul(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={"background_type": "color", "background_value": "#ff0000"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["background_value"] == "#ff0000"

    async def test_renk_tipinde_hex_olmayan_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={"background_type": "color", "background_value": "kirmizi"},
        )
        assert response.status_code == 422

    async def test_gradient_tipinde_hex_olmayan_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={"background_type": "gradient", "background_value": "sol-sag"},
        )
        assert response.status_code == 422

    async def test_gorsel_tipinde_url_kabul(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={
                "background_type": "image",
                "background_value": "https://ornek.com/arka-plan.png",
            },
        )

        assert response.status_code == 200, response.text
        assert (
            response.json()["data"]["background_value"]
            == "https://ornek.com/arka-plan.png"
        )

    async def test_gorsel_tipinde_hex_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={"background_type": "image", "background_value": "#ff0000"},
        )
        assert response.status_code == 422

    async def test_gorsel_tipinde_http_olmayan_422(self, auth_client):
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={
                "background_type": "image",
                "background_value": "javascript:alert(1)",
            },
        )
        assert response.status_code == 422

    async def test_gorsel_urlinde_parantez_422(self, auth_client):
        """Deger CSS'e url(...) icinde giriyor; stil enjeksiyonuna acik olurdu."""
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={
                "background_type": "image",
                "background_value": "https://ornek.com/a(1).png",
            },
        )
        assert response.status_code == 422

    async def test_tip_gonderilmezse_dogrulanmaz(self, auth_client):
        """Kismi guncellemede diger alanin kayitli degeri burada bilinmiyor."""
        response = await auth_client.put(
            "/api/v1/profile/update",
            json={"background_value": "#00ff00"},
        )
        assert response.status_code == 200, response.text

    async def test_onboarding_adiminda_da_gecerli(self, auth_client):
        response = await auth_client.post(
            "/api/v1/profile/complete-step-4",
            json={"background_type": "image", "background_value": "#ff0000"},
        )
        assert response.status_code == 422

    async def test_onboarding_varsayilanlari_gecerli(self, auth_client):
        """Yalnizca renk gonderildiginde varsayilanlar (color/#ffffff) uyumlu."""
        response = await auth_client.post(
            "/api/v1/profile/complete-step-4",
            json={"theme_color": "#123456"},
        )
        assert response.status_code == 200, response.text
