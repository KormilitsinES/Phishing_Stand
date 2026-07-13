# phishing_stand/deploy/steps/docker_compose.py
"""Генерация docker-compose.yml и запуск контейнеров."""
from __future__ import annotations

import time
from pathlib import Path
from string import Template

from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import console
from phishing_stand.utils import compose_command, run


COMPOSE_TEMPLATE = """# Docker Compose для Phishing Stand
# Сгенерировано автоматически

services:
  gophish:
    image: gophish/gophish:latest
    container_name: ${GOPHISH_BACKEND}
    restart: unless-stopped
    volumes:
      - ./gophish/gophish.db:/opt/gophish/gophish.db
      - ./certs/live/${BASE_DOMAIN}/fullchain.pem:/opt/gophish/gophish.crt:ro
      - ./certs/live/${BASE_DOMAIN}/privkey.pem:/opt/gophish/gophish.key:ro
    ports:
      - "3333:3333"
    environment:
      - GOPHISH_INITIAL_ADMIN_PASSWORD=admin
    networks:
      - phishing-net

  evilginx2:
    image: evilginx2/evilginx2:latest
    container_name: ${EVILGINX_BACKEND}
    restart: unless-stopped
    volumes:
      - ./evilginx2/phishlets:/app/phishlets
      - ./evilginx2/data:/root/.evilginx
      - ./certs/live/${EVIL_DOMAIN}/fullchain.pem:/app/certs/fullchain.pem:ro
      - ./certs/live/${EVIL_DOMAIN}/privkey.pem:/app/certs/privkey.pem:ro
    ports:
      - "443:443"
      - "33333:33333"
    networks:
      - phishing-net

  postfix:
    image: boky/postfix:latest
    container_name: ${POSTFIX_BACKEND}
    restart: unless-stopped
    volumes:
      - ./postfix/dkim:/etc/opendkim/keys
      - ./certs/live/${BASE_DOMAIN}/fullchain.pem:/etc/ssl/certs/mail.crt:ro
      - ./certs/live/${BASE_DOMAIN}/privkey.pem:/etc/ssl/private/mail.key:ro
    environment:
      - MAILNAME=${MX_DOMAIN}
      - RELAYHOST=
    ports:
      - "25:25"
      - "587:587"
    networks:
      - phishing-net

  nginx:
    image: nginx:alpine
    container_name: nginx
    restart: unless-stopped
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs/live/${BASE_DOMAIN}/fullchain.pem:/etc/nginx/certs/fullchain.pem:ro
      - ./certs/live/${BASE_DOMAIN}/privkey.pem:/etc/nginx/certs/privkey.pem:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - gophish
      - evilginx2
    networks:
      - phishing-net

networks:
  phishing-net:
    driver: bridge
"""


class DockerComposeStep(Step):
    name = "docker_compose"
    description = "Запуск контейнеров"
    depends_on = ["certbot"]
    requires_root = True

    COMPOSE_FILE = Path("docker-compose.yml")

    def execute(self) -> bool:
        # 1. Генерируем docker-compose.yml
        if not self._generate_compose_file():
            return False

        # 2. Создаём необходимые директории
        self._create_directories()

        # 3. Запускаем контейнеры
        if not self._start_containers():
            return False

        # 4. Ждём готовности
        self._wait_for_containers()

        self.log.success("Все контейнеры запущены")
        return True

    def _generate_compose_file(self) -> bool:
        """Генерируем docker-compose.yml из шаблона."""
        self.log.info("Генерирую docker-compose.yml...")

        template = Template(COMPOSE_TEMPLATE)
        content = template.safe_substitute(
            BASE_DOMAIN=self.settings.BASE_DOMAIN,
            TRACK_DOMAIN=self.settings.TRACK_DOMAIN,
            EVIL_DOMAIN=self.settings.EVIL_DOMAIN,
            MX_DOMAIN=self.settings.MX_DOMAIN,
            GOPHISH_BACKEND=self.settings.GOPHISH_BACKEND,
            POSTFIX_BACKEND=self.settings.POSTFIX_BACKEND,
            EVILGINX_BACKEND=self.settings.EVILGINX_BACKEND,
        )

        self.COMPOSE_FILE.write_text(content, encoding="utf-8")
        self.log.success(f"✓ {self.COMPOSE_FILE} сгенерирован")
        return True

    def _create_directories(self) -> None:
        """Создаём директории для volumes."""
        dirs = [
            Path("gophish"),
            Path("evilginx2/phishlets"),
            Path("evilginx2/data"),
            Path("postfix/dkim"),
            Path("nginx"),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            self.log.debug(f"Создана директория: {d}")

        # Создаём пустую БД Gophish, если её нет
        db_file = Path("gophish/gophish.db")
        if not db_file.exists():
            db_file.touch()
            db_file.chmod(0o666)

        # Создаём базовый nginx.conf
        nginx_conf = Path("nginx/nginx.conf")
        if not nginx_conf.exists():
            nginx_conf.write_text(self._generate_nginx_conf(), encoding="utf-8")

    def _generate_nginx_conf(self) -> str:
        """Генерируем базовый nginx.conf."""
        return f"""events {{
    worker_connections 1024;
}}

http {{
    upstream gophish {{
        server {self.settings.GOPHISH_BACKEND}:3333;
    }}

    upstream evilginx {{
        server {self.settings.EVILGINX_BACKEND}:443;
    }}

    server {{
        listen 80;
        server_name {self.settings.BASE_DOMAIN};
        return 301 https://$server_name$request_uri;
    }}

    server {{
        listen 443 ssl;
        server_name {self.settings.BASE_DOMAIN};

        ssl_certificate /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        location / {{
            proxy_pass http://gophish;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }}
    }}

    server {{
        listen 443 ssl;
        server_name {self.settings.TRACK_DOMAIN};

        ssl_certificate /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        location / {{
            proxy_pass http://gophish;
            proxy_set_header Host $host;
        }}
    }}
}}
"""

    def _start_containers(self) -> bool:
        """Запускаем docker compose up."""
        self.log.info("Запускаю контейнеры...")
        cmd = compose_command()
        r = run([*cmd, "up", "-d"], check=False, timeout=300)

        if not r.ok:
            self.log.error(f"Не удалось запустить контейнеры:\n{r.stderr}")
            return False

        return True

    def _wait_for_containers(self, timeout: int = 60) -> None:
        """Ждём, пока контейнеры станут готовы."""
        self.log.info("Ожидаю готовности контейнеров...")
        start = time.time()

        while time.time() - start < timeout:
            cmd = compose_command()
            r = run([*cmd, "ps", "--format", "json"], check=False, timeout=10)
            if r.ok:
                # Проверяем, что все контейнеры запущены
                import json
                try:
                    containers = [json.loads(line) for line in r.stdout.strip().split("\n") if line]
                    all_running = all(c.get("State") == "running" for c in containers)
                    if all_running and len(containers) >= 4:
                        self.log.success("✓ Все контейнеры запущены")
                        return
                except (json.JSONDecodeError, KeyError):
                    pass
            time.sleep(2)

        self.log.warning("Не все контейнеры готовы, но продолжаем")