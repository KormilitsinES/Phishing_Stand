# phishing_stand/deploy/steps/certbot.py
"""Получение SSL-сертификатов Let's Encrypt."""
from __future__ import annotations

import shutil
from pathlib import Path

from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import console
from phishing_stand.utils import run


class CertbotStep(Step):
    name = "certbot"
    description = "Получение SSL-сертификатов"
    depends_on = ["generate_env"]
    requires_root = True

    CERTS_DIR = Path("certs")

    def pre_check(self) -> bool:
        """Проверяем, что certbot установлен."""
        return shutil.which("certbot") is not None

    def execute(self) -> bool:
        # 1. Устанавливаем certbot, если его нет
        if not self.pre_check():
            if not self._install_certbot():
                return False

        # 2. Проверяем DNS-записи
        if not self._check_dns_records():
            console().print(
                "[yellow]⚠ DNS-записи не настроены. Сертификаты не будут получены.[/]\n"
                "  Продолжить без сертификатов? (стенд будет работать на self-signed)"
            )
            import typer
            if not typer.confirm("Продолжить?", default=True):
                return False
            self._generate_self_signed()
            return True

        # 3. Создаём директорию для сертификатов
        self.CERTS_DIR.mkdir(parents=True, exist_ok=True)

        # 4. Получаем сертификаты для всех доменов
        domains = [
            self.settings.BASE_DOMAIN,
            self.settings.TRACK_DOMAIN,
            self.settings.EVIL_DOMAIN,
            self.settings.MX_DOMAIN,
        ]

        for domain in domains:
            if not self._obtain_certificate(domain):
                return False

        self.log.success("Все SSL-сертификаты получены")
        return True

    def _install_certbot(self) -> bool:
        self.log.info("Устанавливаю certbot...")
        r = run(["apt-get", "install", "-y", "-qq", "certbot"], check=False, timeout=300)
        if not r.ok:
            self.log.error(f"Не удалось установить certbot: {r.stderr}")
            return False
        return True

    def _check_dns_records(self) -> bool:
        """Проверяем, что все домены резолвятся в IP сервера."""
        import socket

        expected_ip = self.settings.VPS_IP
        domains = [
            self.settings.BASE_DOMAIN,
            self.settings.TRACK_DOMAIN,
            self.settings.EVIL_DOMAIN,
            self.settings.MX_DOMAIN,
        ]

        all_ok = True
        for domain in domains:
            try:
                resolved_ip = socket.gethostbyname(domain)
                if resolved_ip != expected_ip:
                    self.log.warning(
                        f"Домен {domain} резолвится в {resolved_ip}, ожидался {expected_ip}"
                    )
                    all_ok = False
                else:
                    self.log.debug(f"✓ {domain} → {resolved_ip}")
            except socket.gaierror:
                self.log.warning(f"Домен {domain} не резолвится")
                all_ok = False

        return all_ok

    def _obtain_certificate(self, domain: str) -> bool:
        """Получить сертификат для одного домена."""
        self.log.info(f"Получаю сертификат для {domain}...")

        # Проверяем, есть ли уже сертификат
        cert_path = self.CERTS_DIR / "live" / domain / "fullchain.pem"
        if cert_path.exists():
            self.log.info(f"Сертификат для {domain} уже существует, пропускаю")
            return True

        # Запускаем certbot в standalone режиме
        r = run(
            [
                "certbot",
                "certonly",
                "--standalone",
                "--non-interactive",
                "--agree-tos",
                "--email",
                self.settings.ADMIN_EMAIL,
                "-d",
                domain,
                "--cert-path",
                str(self.CERTS_DIR / "live" / domain),
                "--key-path",
                str(self.CERTS_DIR / "live" / domain),
                "--fullchain-path",
                str(self.CERTS_DIR / "live" / domain / "fullchain.pem"),
                "--chain-path",
                str(self.CERTS_DIR / "live" / domain / "chain.pem"),
            ],
            check=False,
            timeout=120,
        )

        if not r.ok:
            self.log.error(f"Не удалось получить сертификат для {domain}:\n{r.stderr}")
            return False

        self.log.success(f"✓ Сертификат для {domain} получен")
        return True

    def _generate_self_signed(self) -> bool:
        """Генерируем self-signed сертификаты (fallback)."""
        self.log.warning("Генерирую self-signed сертификаты...")

        domains = [
            self.settings.BASE_DOMAIN,
            self.settings.TRACK_DOMAIN,
            self.settings.EVIL_DOMAIN,
            self.settings.MX_DOMAIN,
        ]

        for domain in domains:
            cert_dir = self.CERTS_DIR / "live" / domain
            cert_dir.mkdir(parents=True, exist_ok=True)

            r = run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-nodes",
                    "-days",
                    "365",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    str(cert_dir / "privkey.pem"),
                    "-out",
                    str(cert_dir / "fullchain.pem"),
                    "-subj",
                    f"/CN={domain}",
                ],
                check=False,
            )

            if not r.ok:
                self.log.error(f"Не удалось сгенерировать self-signed для {domain}")
                return False

        self.log.warning("Self-signed сертификаты созданы (не рекомендуются для продакшена)")
        return True