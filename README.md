# scratchpost-demo

A live, reproducible demonstration of what happens when several AI coding
agents work in one workspace — with and without
[ScratchPost](https://github.com/saksham-sin/scratchpost).

Two microservices live side by side:

- `auth-service` — Spring Boot + **Liquibase** (`<changeSet id="N">`)
- `payment-service` — Spring Boot + **Flyway** (`V<N>__*.sql`)

Both use *sequenced* database migrations. That is the whole point of the demo:
two agents can each write a perfectly valid migration, Git can merge them
without a single textual conflict, and the build still breaks because both
claimed sequence number `200`.

See [`docs/DEMO_REPORT.md`](docs/DEMO_REPORT.md) for the full walkthrough with
transcripts and screenshots.
