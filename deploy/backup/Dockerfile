FROM alpine:3.22.0 AS age-download

ARG TARGETARCH
ARG AGE_VERSION=1.3.2

RUN apk add --no-cache ca-certificates curl tar \
    && mkdir -p /out \
    && case "$TARGETARCH" in \
        amd64) age_archive="age-v${AGE_VERSION}-linux-amd64.tar.gz"; age_sha256="cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10" ;; \
        arm64) age_archive="age-v${AGE_VERSION}-linux-arm64.tar.gz"; age_sha256="6b8dc4333c53a5a57c9e5834e3a48f92605d7154014cd07269ff3327db5d37f4" ;; \
        *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
      esac \
    && curl --fail --location --silent --show-error \
      "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/${age_archive}" \
      --output /tmp/age.tar.gz \
    && echo "${age_sha256}  /tmp/age.tar.gz" | sha256sum -c -s \
    && tar --extract --gzip --file /tmp/age.tar.gz --directory /tmp \
    && install --mode=0555 "/tmp/age/age" /out/age \
    && install --mode=0555 "/tmp/age/age-keygen" /out/age-keygen

FROM postgres:18.6-alpine

COPY --from=age-download /out/age /usr/local/bin/age
COPY --from=age-download /out/age-keygen /usr/local/bin/age-keygen
COPY deploy/backup/acervo_backup.py /usr/local/lib/acervo-backup/acervo_backup.py

RUN apk add --no-cache openssh-client python3 \
    && addgroup -g 10001 acervo \
    && adduser -D -H -u 10001 -G acervo acervo \
    && chmod 0555 /usr/local/lib/acervo-backup/acervo_backup.py \
    && mkdir -p /source-media /target-media /source-settings /restored-settings /backups \
    && chown -R 10001:10001 /source-media /target-media /source-settings /restored-settings /backups

USER 10001:10001

ENTRYPOINT ["python3", "/usr/local/lib/acervo-backup/acervo_backup.py"]
