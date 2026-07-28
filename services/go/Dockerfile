FROM golang:1.23-alpine AS builder
WORKDIR /build
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go test ./... && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o server ./cmd/server/

FROM alpine:3.21
WORKDIR /srv
COPY --from=builder /build/server ./server
EXPOSE 8080
CMD ["./server"]
