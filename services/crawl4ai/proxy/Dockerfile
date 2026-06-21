FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY main.go go.mod /app/
RUN go build -o /crawl-proxy main.go

FROM alpine:3.21
COPY --from=builder /crawl-proxy /root/crawl-proxy
EXPOSE 8000
ENTRYPOINT ["/root/crawl-proxy"]
