FROM boky/postfix

RUN apt-get update && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/custom-entrypoint.sh
COPY main.cf.template /etc/postfix/main.cf.template
COPY header_checks /etc/postfix/header_checks

RUN chmod +x /usr/local/bin/custom-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/custom-entrypoint.sh"]