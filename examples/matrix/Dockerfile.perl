# Perl runtime column.
FROM perl:5.38-slim
COPY adapters/perl /src/perl
WORKDIR /src/perl
CMD ["sh","-c","perl example/hash_connector.pl > /shared/perl.json && echo 'perl: emitted /shared/perl.json'"]
