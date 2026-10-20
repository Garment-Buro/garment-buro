# Build the published security release from verified upstream source. No MinIO
# binary image, download mirror or mutable source branch is required.
FROM --platform=$BUILDPLATFORM golang:1.27.2-bookworm@sha256:5cf287a799e6b94384bad13d16b14904c531f51ba65792237e122ce42b392f61 AS build

ARG TARGETARCH
ENV GOTOOLCHAIN=local CGO_ENABLED=0 GOMAXPROCS=2 GOMEMLIMIT=1500MiB
WORKDIR /build

COPY healthcheck/ /build/healthcheck/
RUN cd /build/healthcheck \
    && go test -count=1 ./... \
    && GOOS=linux GOARCH=$TARGETARCH go build -trimpath -ldflags="-s -w" -o /out/minio-healthcheck .

ADD --checksum=sha256:45521908307306e925c98d629e1c17d78c8b72b6ee242b1bfb1409f7d8ee5841 https://codeload.github.com/minio/minio/tar.gz/9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a /build/source.tar.gz
RUN mkdir /build/minio \
    && tar -xzf /build/source.tar.gz --strip-components=1 -C /build/minio
WORKDIR /build/minio
RUN go mod download \
    && go mod verify \
    && GOOS=linux GOARCH=$TARGETARCH go build -p 2 -mod=readonly -trimpath -buildvcs=false \
       -ldflags="-s -w -X github.com/minio/minio/cmd.Version=2025-10-15T17:29:55Z -X github.com/minio/minio/cmd.ReleaseTag=RELEASE.2025-10-15T17-29-55Z.garment1 -X github.com/minio/minio/cmd.CommitID=9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a -X github.com/minio/minio/cmd.ShortCommitID=9e49d5e7a648f -X github.com/minio/minio/cmd.CopyrightYear=2025" \
       -o /out/minio . \
    && mkdir -p /runtime/data /runtime/tmp /runtime/root \
    && chmod 1777 /runtime/tmp

FROM scratch
LABEL org.opencontainers.image.title="Garment Buro MinIO" \
      org.opencontainers.image.version="2025-10-15-garment1" \
      org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

COPY --from=build /runtime/ /
COPY --from=build /out/minio /out/minio-healthcheck /usr/local/bin/
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build /usr/local/go/lib/time/zoneinfo.zip /zoneinfo.zip
COPY --from=build /build/minio/LICENSE /usr/share/licenses/minio/LICENSE
COPY --from=build /build/source.tar.gz /usr/share/minio/source.tar.gz

# Retain the old image's numeric ownership contract for existing data volumes.
# Production Docker itself runs rootless; changing file ownership is a separate
# storage migration, never an implicit recursive chown at application startup.
USER 0:0
ENV HOME=/root ZONEINFO=/zoneinfo.zip MINIO_UPDATE=off
EXPOSE 9000 9001
VOLUME ["/data"]
HEALTHCHECK --interval=5s --timeout=5s --start-period=20s --retries=20 CMD ["/usr/local/bin/minio-healthcheck"]
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
