# Ruby runtime column.
FROM ruby:3.2-slim
COPY adapters/ruby /src/ruby
WORKDIR /src/ruby
CMD ["sh","-c","ruby example/hash_connector.rb > /shared/ruby.json && echo 'ruby: emitted /shared/ruby.json'"]
