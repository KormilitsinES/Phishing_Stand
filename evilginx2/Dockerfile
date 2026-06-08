FROM golang:1.21-alpine AS builder

RUN apk add --no-cache git make
RUN git clone https://github.com/kgretzky/evilginx2.git /app
WORKDIR /app
RUN make

FROM alpine:latest
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/evilginx .
COPY --from=builder /app/phishlets ./phishlets

# Создаем директорию для данных
RUN mkdir -p /app/.evilginx

EXPOSE 443 80 33333
ENTRYPOINT ["./evilginx", "-developer", "-p", "/app/phishlets"]