# phishing_stand/deploy/steps/dkim.py
"""Генерация DKIM-ключей для Postfix."""
from __future__ import annotations

from pathlib import Path

from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import get_logger
from phishing_stand.utils import run


class DKIMStep(Step):
    name = "dkim"
    description = "Генерация DKIM-ключей"
    depends_on = ["docker_compose"]
    requires_root = True

    DKIM_DIR = Path("postfix/dkim")

    def execute(self) -> bool:
        # 1. Создаём директорию
        self.DKIM_DIR.mkdir(parents=True, exist_ok=True)

        # 2. Проверяем, есть ли уже ключи
        selector = "mail"
        private_key = self.DKIM_DIR / f"{selector}.private"
        txt_record = self.DKIM_DIR / f"{selector}.txt"

        if private_key.exists() and txt_record.exists():
            self.log.info("DKIM-ключи уже существуют, пропускаю генерацию")
        else:
            # 3. Генерируем ключи
            if not self._generate_dkim_keys(selector):
                return False

        # 4. Выводим TXT-запись для DNS
        self._print_dns_instructions(selector)

        self.log.success("DKIM-ключи готовы")
        return True

    def _generate_dkim_keys(self, selector: str) -> bool:
        """Генерируем DKIM-ключи через opendkim-genkey."""
        self.log.info(f"Генерирую DKIM-ключи (selector: {selector})...")

        # Устанавливаем opendkim-tools, если нужно
        r = run(["which", "opendkim-genkey"], check=False)
        if not r.ok:
            self.log.info("Устанавливаю opendkim-tools...")
            r = run(
                ["apt-get", "install", "-y", "-qq", "opendkim-tools"],
                check=False,
                timeout=120,
            )
            if not r.ok:
                self.log.error(f"Не удалось установить opendkim-tools: {r.stderr}")
                return False

        # Генерируем ключ
        r = run(
            [
                "opendkim-genkey",
                "--selector",
                selector,
                "--domain",
                self.settings.BASE_DOMAIN,
                "--bits",
                "2048",
                "--directory",
                str(self.DKIM_DIR),
            ],
            check=False,
        )

        if not r.ok:
            self.log.error(f"Не удалось сгенерировать DKIM-ключи:\n{r.stderr}")
            return False

        # Переименовываем файлы
        generated_private = self.DKIM_DIR / f"{selector}.private"
        generated_txt = self.DKIM_DIR / f"{selector}.txt"

        if generated_private.exists():
            generated_private.chmod(0o600)
            self.log.debug(f"Приватный ключ: {generated_private}")

        return True

    def _print_dns_instructions(self, selector: str) -> None:
        """Выводим инструкции по настройке DNS."""
        txt_file = self.DKIM_DIR / f"{selector}.txt"
        if not txt_file.exists():
            return

        content = txt_file.read_text(encoding="utf-8")
        # Извлекаем TXT-запись
        # Формат: mail._domainkey IN TXT ( "v=DKIM1; k=rsa; p=..." )
        import re
        match = re.search(r'"([^"]+)"', content)
        if match:
            txt_value = match.group(1)
        else:
            txt_value = content.strip()

        print()
        print(
            f"[bold cyan]DKIM TXT-запись для DNS:[/]\n"
            f"  Имя:  [yellow]{selector}._domainkey.{self.settings.BASE_DOMAIN}[/]\n"
            f"  Тип:  [yellow]TXT[/]\n"
            f"  Значение:\n"
            f"    [green]{txt_value}[/]"
        )
        print()
        print(
            "[bold]Также добавьте MX-запись:[/]\n"
            f"  Имя:  [yellow]{self.settings.BASE_DOMAIN}[/]\n"
            f"  Тип:  [yellow]MX[/]\n"
            f"  Значение: [green]10 {self.settings.MX_DOMAIN}.[/]"
        )
        print()