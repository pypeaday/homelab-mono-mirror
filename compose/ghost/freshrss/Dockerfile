# PHP2Shell patch layer (CVE-2026-109618/109619) — bumps php8.4 to >=8.4.27
# (trixie-security) on top of the pinned upstream image until freshrss
# publishes a rebuilt tag. Covers libapache2-mod-php8.4 (mod_php = the
# highest-risk SAPI for this CVE).
FROM freshrss/freshrss:1.30.1
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade -y 'php8.4*' libapache2-mod-php8.4 \
 && rm -rf /var/lib/apt/lists/*
