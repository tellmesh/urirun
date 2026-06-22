# PHP runtime column.
FROM php:8.2-cli
COPY adapters/php /src/php
WORKDIR /src/php
CMD ["sh","-c","php example/hash-connector.php > /shared/php.json && echo 'php: emitted /shared/php.json'"]
