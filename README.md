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

## The result

| | Case 1 — plain `git` | Case 2 — ScratchPost |
|---|---|---|
| PR #1 | `MERGEABLE` / `CLEAN` | `MERGEABLE` / `CLEAN` |
| PR #2 | `MERGEABLE` / `CLEAN` | `MERGEABLE` / `CLEAN` |
| `main` after both merges | ❌ **broken** | ✅ **valid** |
| Duplicate `changeSet id=200` | merged silently | blocked pre-commit |
| Who fixed it | a human, after `main` went red | the agent, in its own session |

Case 1's broken state is preserved on
[`case1-broken-main`](../../tree/case1-broken-main). `main` holds the Case 2
result — `changeSet 200` from agent 1, `changeSet 201` from agent 2, validator
green.

## Reproduce

```bash
git clone https://github.com/saksham-sin/scratchpost-demo.git case1
cd case1
git checkout -b feat-auth-oauth      # agent 1
git checkout -b feat-payment-refund   # agent 2 — same folder, HEAD moves
# both insert changeSet id="200" at different anchors, merge both
python3 scripts/validate-migrations.py   # fails
```

```bash
git clone https://github.com/saksham-sin/scratchpost-demo.git case2
cd case2
sp init
sp run --agent agent_1 -- bash
sp run --agent agent_2 -- bash
# both insert changeSet id="200"; agent_1 commits, agent_2 is blocked
sp resequence --agent agent_2 --file ./auth-service/src/main/resources/db/dbchangelog.xml --from 200 --to 201
python3 scripts/validate-migrations.py   # passes
```

See [`docs/DEMO_REPORT.md`](docs/DEMO_REPORT.md) for the full walkthrough with
transcripts.
