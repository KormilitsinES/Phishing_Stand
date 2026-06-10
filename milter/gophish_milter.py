#!/usr/bin/env python3
import Milter
import uuid
import socket
import logging
import sys

class GoPhishMilter(Milter.Milter):
    def __init__(self):
        self.message_id = None
        self.id = Milter.uniqueID()

    # Этот метод вызывается для каждого заголовка письма
    @Milter.nocallback
    def header(self, name, value):
        if name.lower() == 'message-id':
            self.message_id = value
            # Проверяем, содержит ли Message-ID признаки GoPhish
            if 'gophish' in value.lower() or '@gophish' in value.lower():
                # Генерируем новый Message-ID в стиле Outlook
                # Формат: <UUID@hostname>
                new_message_id = f"<{str(uuid.uuid4())}@{socket.getfqdn()}>"
                self.replace_header(name, new_message_id)
                logging.info(f"Replaced Message-ID: {value} -> {new_message_id}")
        return Milter.CONTINUE

    # Этот метод вызывается в конце SMTP-транзакции, когда письмо полностью принято
    def eom(self):
        # Если Message-ID не был изменен (например, его вообще не было), добавляем свой
        if not self.message_id:
            new_message_id = f"<{str(uuid.uuid4())}@{socket.getfqdn()}>"
            self.addheader('Message-ID', new_message_id)
            logging.info( f"Added new Message-ID: {new_message_id}")
        return Milter.ACCEPT

def main():
    # Путь к сокету, через который Postfix будет общаться с milter'ом
    socket_name = "inet:8892@0.0.0.0"

    # Регистрируем milter
    Milter.factory = GoPhishMilter
    Milter.set_flags(Milter.ADDHDRS | Milter.CHGHDRS)

    print(f"Starting GoPhish Milter on {socket_name}")
    sys.stdout.flush()

    # Запускаем milter в бесконечном цикле
    Milter.runmilter("gophishmilter", socket_name, 60)
    print("Milter shutdown")

if __name__ == "__main__":
    main()