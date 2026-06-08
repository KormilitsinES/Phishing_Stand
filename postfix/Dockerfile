FROM boky/postfix

RUN apk add --no-cache gettext

COPY entrypoint.sh /usr/local/bin/custom-entrypoint.sh
COPY main.cf.template /etc/postfix/main.cf.template
COPY header_checks /etc/postfix/header_checks

RUN chmod +x /usr/local/bin/custom-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/custom-entrypoint.sh"]
