#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shutil
import tarfile
import re
import time
import urllib.request
from pathlib import Path


PARENT_DIR = Path(__file__).parent.resolve()
STATE_FILE = PARENT_DIR / ".deploy_state"
ENV_FILE = PARENT_DIR / ".env"
EXPORT_ARCHIVE_NAME = "phishing_stand_backup.tar.gz"


STEPS = [
    (1, "install_deps", "Проверка и установка системных зависимостей"),
    (2, "prepare_dirs", "Создание необходимых файлов и директорий"),
    (3, "configure_compose", "Конфигурация доменов и генерация docker-compose.yml"),
    (4, "get_certs", "Получение Wildcard-сертификата (DNS-01)"),
    (5, "build_run", "Сборка и запуск контейнеров"),
    (6, "print_info", "Вывод информации о развертывании и DNS-записях"),
]


def load_env():
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip('"\'')


def is_step_completed(step_num):
    if not STATE_FILE.exists():
        return False
    with open(STATE_FILE, "r") as f:
        return str(step_num) in [line.strip() for line in f]


def mark_step_completed(step_num):
    with open(STATE_FILE, "a") as f:
        f.write(f"{step_num}\n")


def reset_state(from_step=1):
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            lines = [line.strip() for line in f if int(line.strip()) < from_step]
        with open(STATE_FILE, "w") as f:
            for line in lines:
                f.write(f"{line}\n")
    print(f"[+] Состояние сброшено для шагов >= {from_step}.")


def run_command(cmd, shell=True):
    print(f"[*] Выполнение: {cmd}")
    result = subprocess.run(cmd, shell=shell, capture_output=False)
    if result.returncode != 0:
        print(f"[-] Ошибка выполнения команды: {cmd}")
        sys.exit(1)


def step_install_deps():
    print("[*] Проверка и установка системных зависимостей...")
    run_command("apt-get update -qq")
    run_command("apt-get install -y -qq curl gettext ca-certificates gnupg lsb-release")

    if shutil.which("docker") is None:
        print("[*] Установка Docker и Docker Compose...")
        run_command("install -m 0755 -d /etc/apt/keyrings")
        run_command(
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg")
        run_command("chmod a+r /etc/apt/keyrings/docker.gpg")
        run_command(
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \\"$VERSION_CODENAME\\") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null')
        run_command("apt-get update -qq")
        run_command(
            "apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin")
        print("[+] Docker и Docker Compose успешно установлены.")
    else:
        print("[+] Docker уже установлен.")


def step_prepare_dirs():
    print("[*] Создание необходимых файлов и директорий...")
    dirs = [
        PARENT_DIR / "postfix" / "dkim",
        PARENT_DIR / "evilginx2" / "phishlets",
        PARENT_DIR / "evilginx2" / "data",
        PARENT_DIR / "certs",
        PARENT_DIR / "gophish"
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    db_file = PARENT_DIR / "gophish" / "gophish.db"
    if not db_file.exists():
        db_file.touch()
    os.chmod(db_file, 0o666)
    print("[+] Директории созданы.")


def generate_compose():
    template_file = PARENT_DIR / "docker-compose.yml.template"
    if not template_file.exists():
        print("[-] Ошибка: Файл docker-compose.yml.template не найден.")
        sys.exit(1)

    print("[*] Генерация docker-compose.yml...")
    with open(template_file, "r") as f:
        content = f.read()

    def replacer(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, match.group(0))

    content = re.sub(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)', replacer, content)

    with open(PARENT_DIR / "docker-compose.yml", "w") as f:
        f.write(content)
    print("[+] docker-compose.yml успешно сгенерирован.")


def step_configure_compose():
    print("=== Конфигурация доменов ===")
    if ENV_FILE.exists():
        use_existing = input("Файл .env уже существует. Использовать существующие значения? (Y/n): ").strip().lower()
        if use_existing != 'n':
            print("[+] Использованы существующие значения из .env")
            load_env()
            generate_compose()
            return

    base_domain = input("Введите базовый домен (например, my-domain.com): ").strip() or "my-domain.com"
    track_domain = input(
        f"Введите домен для трекинга GoPhish [track.{base_domain}]: ").strip() or f"track.{base_domain}"
    evil_domain = input(f"Введите домен для Evilginx2 [phish.{base_domain}]: ").strip() or f"phish.{base_domain}"
    mx_domain = input(f"Введите MX-домен для почты [mail.{base_domain}]: ").strip() or f"mail.{base_domain}"
    admin_email = input(
        f"Введите Email для Let's Encrypt [support@{base_domain}]: ").strip() or f"support@{base_domain}"
    gophish_backend = input("Введите название для контейнера с GoPhish [mailer-app]: ").strip() or "mailer-app"
    postfix_backend = input("Введите название для контейнера с Postfix [mailer]: ").strip() or "mailer"
    evilginx_backend = input("Введите название для контейнера с Evilginx2 [evilginx2]: ").strip() or "evilginx2"

    print("[*] Определение внешнего IP адреса VPS...")
    try:
        vps_ip = urllib.request.urlopen('https://api.ipify.org', timeout=10).read().decode('utf8').strip()
    except Exception:
        print("[-] Не удалось определить внешний IP адрес VPS.")
        sys.exit(1)

    print(f"[*] Сохранение конфигурации в {ENV_FILE}...")
    with open(ENV_FILE, "w") as f:
        f.write(f"BASE_DOMAIN={base_domain}\n")
        f.write(f"TRACK_DOMAIN={track_domain}\n")
        f.write(f"EVIL_DOMAIN={evil_domain}\n")
        f.write(f"MX_DOMAIN={mx_domain}\n")
        f.write(f"ADMIN_EMAIL={admin_email}\n")
        f.write(f"GOPHISH_BACKEND={gophish_backend}\n")
        f.write(f"POSTFIX_BACKEND={postfix_backend}\n")
        f.write(f"EVILGINX_BACKEND={evilginx_backend}\n")
        f.write(f"VPS_IP={vps_ip}\n")

    load_env()
    generate_compose()


def step_get_certs():
    print("=== Получение Wildcard-сертификата (DNS-01) ===")
    base_domain = os.environ.get("BASE_DOMAIN", "my-domain.com")
    cert_path = PARENT_DIR / "certs" / "live" / base_domain / "fullchain.pem"

    if cert_path.exists():
        cert_action = input(
            "[!] Сертификат уже существует. Пропустить получение или попытаться обновить? (Skip/Update): ").strip().lower()
        if cert_action in ('skip', 's'):
            print("[+] Пропускаем получение сертификата.")
            return

    print("ВНИМАНИЕ: Сейчас запустится Certbot в ручном режиме.")
    print("1. Он выдаст вам значение для TXT-записи.")
    print("2. ОТКРОЙТЕ ВТОРОЙ ТЕРМИНАЛ и добавьте эту TXT-запись у DNS-провайдера.")
    print(f"3. Проверьте применение: dig TXT _acme-challenge.{base_domain} +short")
    print("4. Только после этого возвращайтесь сюда и нажимайте ENTER.")
    print("-------------------------------------------------------")
    input("Нажмите ENTER, когда будете готовы увидеть challenge-запрос...")

    print("\n[*] Запуск Certbot...")
    admin_email = os.environ.get("ADMIN_EMAIL", "support@my-domain.com")
    cmd = [
        "docker", "run", "-it", "--rm",
        "-v", f"{PARENT_DIR}/certs:/etc/letsencrypt",
        "certbot/certbot",
        "certonly", "--manual", "--preferred-challenges", "dns",
        "--email", admin_email,
        "--agree-tos", "--no-eff-email",
        "-d", base_domain, "-d", f"*.{base_domain}"
    ]
    run_command(" ".join(cmd))

    if not cert_path.exists():
        print("[-] Ошибка: Сертификат не был получен. Проверьте логи выше.")
        sys.exit(1)

    archive_dir = PARENT_DIR / "certs" / "archive" / base_domain
    if archive_dir.exists():
        for f in archive_dir.iterdir():
            os.chmod(f, 0o744)
    print("[+] Wildcard-сертификат успешно получен!")


def step_build_run():
    print("=== Сборка и запуск контейнеров ===")
    print("[*] Сборка образов (milter, postfix, nginx, evilginx2, gophish)...")
    run_command("docker compose up -d --build")
    print("[+] Контейнеры запущены. Ожидание инициализации Postfix и генерации DKIM (15 сек)...")
    time.sleep(15)


def step_print_info():
    print("\n=======================================================")
    print(" СТЕНД УСПЕШНО РАЗВЕРНУТ!")
    print("=======================================================")

    base_domain = os.environ.get("BASE_DOMAIN", "my-domain.com")
    mx_domain = os.environ.get("MX_DOMAIN", f"mail.{base_domain}")
    vps_ip = os.environ.get("VPS_IP", "YOUR_VPS_IP")

    print(f"Добавьте следующие записи в панель управления вашего DNS-провайдера:")
    print("-------------------------------------------------------")
    print(f"1. A-записи (укажите IP: {vps_ip}):")
    print(f" Имя: track -> Значение: {vps_ip}")
    print(f" Имя: phish -> Значение: {vps_ip}")
    print(f" Имя: mail -> Значение: {vps_ip}")
    print()
    print("2. MX-запись:")
    print(f" Имя: @ (или оставьте пустым) -> Значение: {mx_domain} (Приоритет: 10)")
    print()
    print("3. TXT-запись (SPF):")
    print(f" Имя: @ -> Значение: v=spf1 ip4:{vps_ip} -all")
    print()

    dkim_file = PARENT_DIR / "postfix" / "dkim" / "default.txt"
    if dkim_file.exists():
        with open(dkim_file, "r") as f:
            content = f.read()
            match = re.search(r'p=(.*)', content)
            if match:
                dkim_value = match.group(1).replace(' ', '').replace('(', '').replace(')', '').replace('"', '').strip()
                print("4. TXT-запись (DKIM):")
                print(f" Имя: default._domainkey -> Значение: v=DKIM1; k=rsa; p={dkim_value}")
            else:
                print("[-] Предупреждение: Не удалось извлечь DKIM ключ. Проверьте: docker compose logs postfix")
    else:
        print("[-] Предупреждение: Файл DKIM ключа не найден. Проверьте: docker compose logs postfix")
    print("-------------------------------------------------------")

    print("\n=== Учетные данные GoPhish ===")
    print("[*] Извлечение пароля из логов GoPhish...")
    time.sleep(5)

    result = subprocess.run(["docker", "compose", "logs", "gophish"], capture_output=True, text=True)
    logs = result.stdout + result.stderr

    password_match = re.search(r'password="([^"]+)"', logs)
    if not password_match:
        password_match = re.search(r'password:\s*(\S+)', logs)
    if not password_match:
        password_lines = [line for line in logs.split('\n') if 'password' in line.lower()]
        for line in password_lines:
            match = re.search(r'[a-zA-Z0-9]{16,}', line)
            if match:
                password_match = match
                break

    if password_match:
        gophish_password = password_match.group(1) if password_match.lastindex else password_match.group(0)
        print("[+] Учетные данные для входа в админку GoPhish:")
        print(" URL: https://127.0.0.1:3333 (через SSH-туннель)")
        print(" Username: admin")
        print(f" Password: {gophish_password}")
    else:
        print("[-] Не удалось автоматически извлечь пароль GoPhish из логов.")
        print("[*] Пожалуйста, проверьте логи вручную: docker compose logs gophish | grep -i password")

    print("\nПолезные команды:")
    print(" - Доступ к админке GoPhish (через SSH-туннель):")
    print(f" ssh -L 3333:127.0.0.1:3333 root@{vps_ip}")
    print(" Затем откройте в браузере: https://127.0.0.1:3333")
    print(" - Доступ к консоли Evilginx2 (через SSH-туннель):")
    print(f" ssh -L 33333:127.0.0.1:33333 root@{vps_ip}")
    print(" - Просмотр логов: docker compose logs -f [имя_сервиса]")
    print("=======================================================")


def export_data():
    print("[*] Создание архива экспорта...")
    archive_path = PARENT_DIR / EXPORT_ARCHIVE_NAME

    files_to_include = []
    paths_to_check = [
        PARENT_DIR / "certs",
        PARENT_DIR / "evilginx2" / "data",
        PARENT_DIR / "evilginx2" / "phishlets",
        PARENT_DIR / "gophish" / "gophish.db",
        ENV_FILE,
        PARENT_DIR / "postfix" / "dkim"
    ]

    for path in paths_to_check:
        if path.exists():
            files_to_include.append(path)

    if not files_to_include:
        print("[-] Нет данных для экспорта.")
        return

    with tarfile.open(archive_path, "w:gz") as tar:
        for path in files_to_include:
            tar.add(path, arcname=path.name)

    print(f"[+] Экспорт успешно завершен: {archive_path}")


def import_data():
    archive_path = PARENT_DIR / EXPORT_ARCHIVE_NAME
    if not archive_path.exists():
        print(f"[-] Архив для импорта не найден: {archive_path}")
        return False

    print(f"[*] Найден архив резервной копии: {archive_path}")
    choice = input("Хотите импортировать данные из архива перед началом развертывания? (Y/n): ").strip().lower()
    if choice in ('n', 'no'):
        return False

    print("[*] Распаковка архива...")
    with tarfile.open(archive_path, "r:gz") as tar:
        # Используем стандартный extractall. Для Python 3.12+ можно добавить filter='data' для безопасности
        try:
            tar.extractall(path=PARENT_DIR, filter='data')
        except TypeError:
            tar.extractall(path=PARENT_DIR)

    print("[+] Данные успешно импортированы.")
    return True


def main():
    if os.geteuid() != 0:
        print("[-] Ошибка: Пожалуйста, запустите скрипт от имени root или через sudo")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Скрипт развертывания Phishing Stand (Postfix, Gophish, Evilginx2, Milter, Nginx)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  sudo python3 deploy.py                  # Полное развертывание с начала
  sudo python3 deploy.py --from 4         # Начать с шага 4 (получение сертификатов)
  sudo python3 deploy.py --only 5         # Выполнить только шаг 5 (сборка и запуск)
  sudo python3 deploy.py --confirm        # Запрашивать подтверждение перед каждым шагом
  sudo python3 deploy.py --skip 4 6       # Пропустить шаги 4 и 6
  sudo python3 deploy.py --export         # Создать резервную копию конфигурации и данных
  sudo python3 deploy.py --import         # Восстановить данные из резервной копии
        """
    )
    parser.add_argument("--from", dest="start_from", type=int, default=1,
                        help="Начать с указанного шага (по умолчанию: 1)")
    parser.add_argument("--only", dest="only_step", type=int, help="Выполнить только указанный шаг")
    parser.add_argument("--reset", action="store_true", help="Сбросить состояние выполнения и начать заново")
    parser.add_argument("--export", action="store_true", help="Экспортировать конфигурацию и данные в архив")
    parser.add_argument("--import", dest="import_data_flag", action="store_true",
                        help="Импортировать конфигурацию и данные из архива")
    parser.add_argument("--confirm", action="store_true",
                        help="Запрашивать подтверждение перед выполнением каждого шага")
    parser.add_argument("--skip", dest="skip_steps", nargs="*", type=int, default=[],
                        help="Пропустить указанные номера шагов")

    args = parser.parse_args()

    if args.export:
        export_data()
        sys.exit(0)

    if args.import_data_flag:
        import_data()
        sys.exit(0)

    if args.reset:
        reset_state(args.start_from)

    if not STATE_FILE.exists() or STATE_FILE.stat().st_size == 0:
        archive_path = PARENT_DIR / EXPORT_ARCHIVE_NAME
        if archive_path.exists():
            print("[!] Обнаружен архив резервной копии в директории скрипта.")
            if import_data():
                print("[+] Импорт завершен. Продолжаем развертывание.")
            else:
                print("[*] Импорт отменен пользователем. Продолжаем развертывание.")

    load_env()

    steps_to_run = []
    if args.only_step:
        steps_to_run = [s for s in STEPS if s[0] == args.only_step]
    else:
        steps_to_run = [s for s in STEPS if s[0] >= args.start_from and s[0] not in args.skip_steps]

    for step_num, step_name, step_desc in steps_to_run:
        if is_step_completed(step_num) and not args.only_step:
            print(f"[+] Шаг {step_num} ({step_name}) уже выполнен. Пропускаем.")
            continue

        print(f"\n=======================================================")
        print(f" Выполнение шага {step_num}: {step_desc}")
        print(f"=======================================================")

        if args.confirm:
            confirm = input(f"Продолжить выполнение шага {step_num}? (Y/n): ").strip().lower()
            if confirm in ('n', 'no'):
                print(f"[*] Шаг {step_num} пропущен пользователем.")
                continue

        load_env()

        step_func = globals().get(f"step_{step_name}")
        if step_func:
            try:
                step_func()
                if not args.only_step:
                    mark_step_completed(step_num)
                print(f"[+] Шаг {step_num} успешно завершен.")
            except Exception as e:
                print(f"[-] Ошибка на шаге {step_num}: {e}")
                print(f"[*] Исправьте проблему и запустите скрипт снова с аргументом --from {step_num}")
                sys.exit(1)
        else:
            print(f"[-] Функция для шага {step_name} не найдена.")
            sys.exit(1)

    print("\n=======================================================")
    print(" РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО УСПЕШНО!")
    print("=======================================================")


if __name__ == "__main__":
    main()