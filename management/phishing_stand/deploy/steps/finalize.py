# phishing_stand/deploy/steps/finalize.py
"""Финальная проверка и вывод инструкций."""
from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import console, console_out
from phishing_stand.utils import compose_command, run


class FinalizeStep(Step):
    name = "finalize"
    description = "Финальная проверка"
    depends_on = ["dkim"]
    requires_root = False

    def execute(self) -> bool:
        # 1. Проверяем состояние контейнеров
        self._check_containers()

        # 2. Выводим итоговую информацию
        self._print_summary()

        self.log.success("Развёртывание завершено!")
        return True

    def _check_containers(self) -> None:
        """Проверяем, что все контейнеры запущены."""
        cmd = compose_command()
        r = run([*cmd, "ps"], check=False, timeout=10)

        if r.ok:
            self.log.debug("Состояние контейнеров:\n" + r.stdout)
        else:
            self.log.warning("Не удалось получить состояние контейнеров")

    def _print_summary(self) -> None:
        """Выводим итоговую таблицу с URL и инструкциями."""
        table = Table(title="✓ Стенд развёрнут успешно", show_header=True, header_style="bold cyan")
        table.add_column("Компонент", style="green")
        table.add_column("URL / Порт", style="yellow")
        table.add_column("Логин / Пароль", style="magenta")

        table.add_row(
            "Gophish (админка)",
            f"https://{self.settings.BASE_DOMAIN}:3333",
            "admin / admin",
        )
        table.add_row(
            "Gophish (трекинг)",
            f"https://{self.settings.TRACK_DOMAIN}",
            "—",
        )
        table.add_row(
            "Evilginx2",
            f"https://{self.settings.EVIL_DOMAIN}:33333",
            "—",
        )
        table.add_row(
            "Postfix (SMTP)",
            f"{self.settings.MX_DOMAIN}:25",
            "—",
        )

        console_out().print()
        console_out().print(table)

        console_out().print()
        console_out().print(
            Panel(
                "[bold]Важные инструкции:[/]\n\n"
                "1. [cyan]Настройте DNS-записи[/]:\n"
                f"   • A-записи для всех доменов → {self.settings.VPS_IP}\n"
                f"   • MX-запись → 10 {self.settings.MX_DOMAIN}.\n"
                "   • TXT-запись для DKIM (см. вывод выше)\n\n"
                "2. [cyan]Смените пароль администратора Gophish[/]:\n"
                "   • Войдите в админку и измените пароль\n\n"
                "3. [cyan]Настройте Evilginx2[/]:\n"
                "   • Добавьте phishlets через веб-интерфейс\n"
                "   • Настройте домены и сертификаты\n\n"
                "4. [cyan]Полезные команды[/]:\n"
                "   • phishing-stand status       — проверка состояния\n"
                "   • phishing-stand export       — экспорт данных\n"
                "   • docker compose logs -f      — логи контейнеров\n"
                "   • docker compose restart      — перезапуск\n",
                title="Следующие шаги",
                border_style="green",
            )
        )