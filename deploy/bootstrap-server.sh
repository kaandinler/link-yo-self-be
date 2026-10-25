#!/usr/bin/env bash
# LinkYoSelf: bos bir Ubuntu sunucusunu (22.04 / 24.04) yigini calistirmaya
# hazirlar. Sunucuda, root olarak, BIR KEZ:
#
#   curl -fsSLO https://raw.githubusercontent.com/kaandinler/link-yo-self-be/main/deploy/bootstrap-server.sh
#   less bootstrap-server.sh        # once okuyun
#   sudo bash bootstrap-server.sh
#
# Tekrar calistirmak guvenli: her adim once durumuna bakiyor, yapilmissa
# atlaniyor.
#
# NE YAPIYOR
#   1. Paketleri guncelliyor; git, jq, ufw, unattended-upgrades kuruyor
#   2. Docker Engine + compose eklentisi (Docker'in kendi apt deposundan)
#   3. `deploy` kullanicisi; root'un SSH anahtarlari ona kopyalaniyor
#   4. SSH: yalnizca anahtar, root girisi kapali
#   5. Guvenlik duvari: yalnizca 22, 80, 443
#   6. Swap (2 GB): web imajini derlerken Next 4 GB'lik makinede zorlaniyor
#   7. Guvenlik guncellemeleri otomatik
#   8. Iki depo /srv/linkyoself altina klonlaniyor
#
# Ayarlar (ortam degiskeni):
#   DEPLOY_USER   varsayilan: deploy
#   APP_DIR       varsayilan: /srv/linkyoself
#   SWAP_SIZE     varsayilan: 2G   (0 = swap olusturma)
#   REPO_BRANCH   varsayilan: main

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR="${APP_DIR:-/srv/linkyoself}"
SWAP_SIZE="${SWAP_SIZE:-2G}"
REPO_BRANCH="${REPO_BRANCH:-main}"
BE_REPO="https://github.com/kaandinler/link-yo-self-be.git"
FE_REPO="https://github.com/kaandinler/link-yo-self-fe.git"

adim() { printf '\n==> %s\n' "$*"; }
bilgi() { printf '    %s\n' "$*"; }
dur() { printf '\nHATA: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || dur "root olarak calistirin: sudo bash $0"
command -v apt-get >/dev/null || dur "yalnizca Debian/Ubuntu destekleniyor"

export DEBIAN_FRONTEND=noninteractive

# --- 1. Paketler -----------------------------------------------------------
adim "Paketler"
apt-get update -q
apt-get upgrade -yq
apt-get install -yq ca-certificates curl git jq ufw unattended-upgrades

# --- 2. Docker -------------------------------------------------------------
adim "Docker"
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    bilgi "zaten kurulu: $(docker --version)"
else
    # Docker'in kendi deposu: Ubuntu'nun docker.io paketinde compose
    # eklentisi ya yok ya da eski; compose dosyalarimiz `!reset` gibi
    # yeni sozdizimi kullaniyor.
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    # shellcheck source=/dev/null
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    bilgi "kuruldu: $(docker --version)"
fi

# --- 3. deploy kullanicisi ---------------------------------------------------
adim "Kullanici: $DEPLOY_USER"
if id "$DEPLOY_USER" >/dev/null 2>&1; then
    bilgi "zaten var"
else
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
    bilgi "olusturuldu (parolasiz; giris yalnizca SSH anahtariyla)"
fi
# DIKKAT: docker grubu fiilen root yetkisi demek. Bu sunucunun tek isi
# bu yigin oldugu icin kabul ediliyor; deploy kullanicisinin anahtari
# root'un anahtari kadar korunmali.
usermod -aG docker "$DEPLOY_USER"

DEPLOY_HOME="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$DEPLOY_HOME/.ssh"
if [ -s /root/.ssh/authorized_keys ]; then
    touch "$DEPLOY_HOME/.ssh/authorized_keys"
    # Yalnizca eksik anahtarlar ekleniyor; tekrar calistirmak cogaltmiyor.
    while IFS= read -r anahtar; do
        [ -n "$anahtar" ] || continue
        grep -qxF "$anahtar" "$DEPLOY_HOME/.ssh/authorized_keys" \
            || echo "$anahtar" >> "$DEPLOY_HOME/.ssh/authorized_keys"
    done < /root/.ssh/authorized_keys
    chown "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_HOME/.ssh/authorized_keys"
    chmod 600 "$DEPLOY_HOME/.ssh/authorized_keys"
fi

# --- 4. SSH ----------------------------------------------------------------
adim "SSH"
# KILITLENMEYE KARSI: deploy kullanicisinin anahtari yokken root girisini
# kapatmak, sunucuya bir daha girememek demek. Bu durumda SSH'a hic
# dokunulmuyor.
if [ ! -s "$DEPLOY_HOME/.ssh/authorized_keys" ]; then
    bilgi "ATLANDI: $DEPLOY_USER icin SSH anahtari yok (root'ta da yok)."
    bilgi "Anahtari $DEPLOY_HOME/.ssh/authorized_keys'e ekleyip betigi yeniden calistirin."
else
    cat > /etc/ssh/sshd_config.d/99-linkyoself.conf <<'SSHD'
# deploy/bootstrap-server.sh tarafindan yazildi.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSHD
    # Yapilandirma bozuksa yeniden yuklemek SSH'i dusururdu; once dogrula.
    sshd -t || { rm -f /etc/ssh/sshd_config.d/99-linkyoself.conf; dur "sshd yapilandirmasi gecersiz; degisiklik geri alindi"; }
    systemctl reload ssh 2>/dev/null || systemctl reload sshd
    bilgi "parola ve root girisi kapali. YENI bir terminalde test edin:"
    bilgi "  ssh $DEPLOY_USER@<sunucu-ip>"
    bilgi "bu oturumu o calismadan KAPATMAYIN."
fi

# --- 5. Guvenlik duvari ------------------------------------------------------
adim "Guvenlik duvari (ufw)"
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw allow 443/udp >/dev/null # HTTP/3
ufw --force enable >/dev/null
bilgi "acik: 22, 80, 443"
# NOT: Docker'in yayinladigi portlar ufw kurallarini atliyor (iptables'a
# kendisi yaziyor). Bu yuzden prod katmaninda Caddy disinda hicbir servis
# port yayinlamiyor; deploy-config workflow'u bunu her PR'da kontrol ediyor.

# --- 6. Swap ---------------------------------------------------------------
adim "Swap"
if [ "$SWAP_SIZE" = "0" ]; then
    bilgi "istenmedi"
elif swapon --show --noheadings | grep -q .; then
    bilgi "zaten var: $(swapon --show --noheadings | awk '{print $1, $3}')"
else
    fallocate -l "$SWAP_SIZE" /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    # Swap yalnizca derleme gibi anlik tepeler icin; uygulama bellegini
    # diske itmesin.
    sysctl -q vm.swappiness=10
    echo 'vm.swappiness=10' > /etc/sysctl.d/99-linkyoself.conf
    bilgi "$SWAP_SIZE olusturuldu"
fi

# --- 7. Otomatik guvenlik guncellemeleri -------------------------------------
adim "Otomatik guvenlik guncellemeleri"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true
bilgi "acik (yeniden baslatma gerektirenler kendiliginden yeniden baslatmiyor)"

# --- 8. Depolar --------------------------------------------------------------
adim "Depolar: $APP_DIR"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$APP_DIR" "$APP_DIR/backups"
for depo in "$BE_REPO" "$FE_REPO"; do
    hedef="$APP_DIR/$(basename "$depo" .git)"
    if [ -d "$hedef/.git" ]; then
        bilgi "zaten var: $hedef"
    else
        sudo -u "$DEPLOY_USER" git clone --branch "$REPO_BRANCH" "$depo" "$hedef"
    fi
done

cat <<SON

Bitti. Siradaki adimlar (ayrintisi docs/DEPLOY.md):

  1. $DEPLOY_USER olarak girin:  ssh $DEPLOY_USER@<sunucu-ip>
  2. cd $APP_DIR/link-yo-self-be
     cp deploy/.env.prod.example .env && chmod 600 .env && nano .env
  3. DNS kayitlari (@, www, api) bu sunucuyu gosterdikten sonra:
     docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
SON
