# ScratchPost Demo — Two Agents, One Repository

> *Stop your parallel coding agents from scratching the same file.*

This repository is a **live, reproducible sample** of what happens when several AI
coding agents work in the same workspace — and what changes when
[ScratchPost](https://github.com/saksham-sin/scratchpost) brokers their commits.

Two agents, two features, one shared Liquibase changelog. The only variable is
whether ScratchPost is in the loop.

| | Case 1 — plain `git` | Case 2 — ScratchPost |
|---|---|---|
| Agent isolation | shared working tree | one worktree per agent |
| Branch state | last writer wins | per-agent branch |
| Sequence collision | **silent** | blocked before commit |
| PR #1 | `MERGEABLE` / `CLEAN` | `MERGEABLE` / `CLEAN` |
| PR #2 | `MERGEABLE` / `CLEAN` | `MERGEABLE` / `CLEAN` |
| `main` after both merges | ❌ **broken** | ✅ **valid** |
| Who caught it | CI, after the fact | the agent, before the commit |

---

## 1. The workspace

```
scratchpost-demo/
├── .ai-context.md                  # shared root context for every agent
├── auth-service/                   # Liquibase
│   └── src/main/resources/db/dbchangelog.xml
├── payment-service/                # Flyway
│   └── src/main/resources/db/migration/V100__*.sql, V101__*.sql
└── scripts/validate-migrations.py  # CI gate: duplicate ids / versions
```

`scripts/validate-migrations.py` is the ground truth. It fails the build if two
migrations claim the same sequence number, regardless of whether Git could merge
them textually.

```console
$ python3 scripts/validate-migrations.py
migration validation passed: all sequence numbers unique
```

Both agents are asked to add a table. Both naturally reach for the next free
Liquibase id: **`200`**.

---

## 2. Case 1 — plain `git`

### 2.1 HEAD tug-of-war

Two agents, one `.git/HEAD`.

```console
$ git branch --show-current   # agent_1 starts work
Switched to a new branch 'feat-auth-oauth'
feat-auth-oauth

$ git branch --show-current   # agent_2 starts work IN THE SAME FOLDER
Switched to a new branch 'feat-payment-refund'
feat-payment-refund

$ git branch --show-current   # agent_1 checks where it is
feat-payment-refund
```

Agent 1 is now committing to agent 2's branch. Nothing errored. Nothing warned.

### 2.2 The collision Git cannot see

The interesting variant is not the one that conflicts. It is the one that merges
cleanly.

Agent 1 inserts `changeSet id="200"` after `changeSet 101`.
Agent 2 inserts `changeSet id="200"` after `changeSet 100`.

Different anchors, so the hunks do not overlap:

```console
$ git merge-tree --write-tree main feat-auth-oauth
  exit 0 -> NO conflict

$ git merge-tree --write-tree main feat-payment-refund
  exit 0 -> NO conflict

$ git merge --no-ff feat-auth-oauth && git merge --no-ff feat-payment-refund
  PR #1 merged cleanly
Auto-merging auth-service/src/main/resources/db/dbchangelog.xml
  PR #2 merged cleanly  <-- git is happy
```

Git is satisfied. The build is not:

```console
$ grep -n 'changeSet id=' auth-service/src/main/resources/db/dbchangelog.xml
8:    <changeSet id="100" author="platform">
19:    <changeSet id="200" author="agent_2">
23:    <changeSet id="101" author="platform">
29:    <changeSet id="200" author="agent_1">

$ python3 scripts/validate-migrations.py
MIGRATION VALIDATION FAILED
  - auth-service/src/main/resources/db/dbchangelog.xml: duplicate changeSet id=200 (claimed twice)
  exit=1
```

### 2.3 The PRs

Both branches were pushed and real pull requests opened.

```console
$ gh pr view 1 --json mergeable,mergeStateStatus
MERGEABLE / CLEAN
$ gh pr view 2 --json mergeable,mergeStateStatus
MERGEABLE / CLEAN
```

**Both PRs reported `MERGEABLE` / `CLEAN` at the same time.** GitHub's merge
check is textual; it has no concept of a sequence namespace.

PR #1 was merged. PR #2 was re-checked:

```console
$ gh pr merge 1 --merge
$ gh pr view 2 --json mergeable,mergeStateStatus
MERGEABLE / CLEAN      # still clean, after PR #1 landed
$ gh pr merge 2 --merge
```

`main` is now broken. The failure is preserved on branch
[`case1-broken-main`](../../tree/case1-broken-main) for inspection:

```console
$ git checkout case1-broken-main && python3 scripts/validate-migrations.py
MIGRATION VALIDATION FAILED
  - auth-service/src/main/resources/db/dbchangelog.xml: duplicate changeSet id=200 (claimed twice)
```

**Cost:** two green PRs, a broken `main`, and a human who has to work out which
agent should renumber — after the fact, with both changes already landed.

---

## 3. Case 2 — ScratchPost

Same repository, same two agents, same task. `sp init` installs managed Git hooks
and starts `scratchpostd`.

### 3.1 Isolation

```console
$ sp status
🐈 ScratchPost · status
  mode fcfs · 2 session(s) · 0 claim(s)
  agent_1 slot 1 · port 31000 · sp/agent_1/1a1e405f388
    /private/tmp/case2/.scratchpost/sessions/agent_1/workspace
  agent_2 slot 2 · port 31100 · sp/agent_2/1a1e405f4f8
    /private/tmp/case2/.scratchpost/sessions/agent_2/workspace
```

Each agent gets its own worktree, its own branch, and its own port band
(`31000` / `31100`) so concurrent `mvn test` runs cannot collide either.

### 3.2 Agent 1 commits

```console
$ agent_1: git commit
SP_NOTICE v1 seq=4 severity=info kind=commit-permit agent=agent_1 \
  message=commit permit 1dcf5b36... issued for . (1 sequence claim(s))
[sp/agent_1/1a1e405f388 6bd7f34] feat(auth): oauth_tokens (changeSet 200)
  exit=0
```

The gate scanned the staged tree, found the new `changeSet id="200"`, and
recorded a claim in the ledger **before** the commit object existed.

### 3.3 Agent 2 is blocked

```console
$ agent_2: git commit
This is a coordination conflict, not a transient Git error.

EVIDENCE
  rule: liquibase.changeset_id
  namespace: case2:auth-service/src/main/resources/db/dbchangelog.xml
  file: auth-service/src/main/resources/db/dbchangelog.xml
  line: 25
  requested value: 200
  reserved by: agent_1 (intent/claim 1)
  lowest_free: 201
  base: f393692a423155f9dac4c41c5377c5f2cfb3f716
  conflicting paths: auth-service/src/main/resources/db/dbchangelog.xml

RESOLUTION
  1. Change the value at auth-service/src/main/resources/db/dbchangelog.xml:25 from 200 to 201.
       sp resequence --agent agent_2 --file ./auth-service/src/main/resources/db/dbchangelog.xml --from 200 --to 201
  2. Re-stage the edited file.
       git -C . add -- auth-service/src/main/resources/db/dbchangelog.xml
  3. Retry the original commit.
       git commit -m "<your original message>"

RETRY CONTRACT
  mode: rerun_original_command
  validation: automatic_on_retry
  max_attempts: 3
  idempotent: true

FORBIDDEN
  - git commit --no-verify
  - editing .scratchpost state
  - force-pushing another agent branch

SP_CONFLICT_JSON={"schema":"sp.conflict.v1","code":"SP_SEQUENCE_COLLISION", ...}

Exit status: 1
```

The agent does not need to be told what to do. The contract names the file, the
line, the value it asked for, who holds it, and the lowest free value.

### 3.4 The agent self-corrects

```console
$ sp resequence --agent agent_2 --file ./auth-service/.../dbchangelog.xml --from 200 --to 201
🐈 ScratchPost · resequence agent_2:./auth-service/src/main/resources/db/dbchangelog.xml from=200 to=201
  staged

$ grep -n 'changeSet id=' <agent_2 worktree>
8:    <changeSet id="100" author="platform">
19:    <changeSet id="101" author="platform">
25:    <changeSet id="201" author="agent_2">

$ agent_2: git commit   # retry the original command
[sp/agent_2/1a1e405f4f8 2182239] feat(payment): refunds (changeSet 201)
  exit=0

$ sp claims
🐈 ScratchPost · claims
  2 sequence claim(s)
  #1 case2:auth-service/src/main/resources/db/dbchangelog.xml 200 committed
    liquibase.changeset_id · held by agent_1
  #2 case2:auth-service/src/main/resources/db/dbchangelog.xml 201 committed
    liquibase.changeset_id · held by agent_2
```

No human, no LLM call inside the daemon, no CI round-trip.

### 3.5 The PRs

PR [#3](https://github.com/saksham-sin/scratchpost-demo/pull/3) and
PR [#4](https://github.com/saksham-sin/scratchpost-demo/pull/4) were opened and
merged in order.

```console
$ gh pr view 3 --json mergeable,mergeStateStatus
MERGEABLE / CLEAN
$ gh pr merge 3 --merge
$ gh pr view 4 --json mergeable,mergeStateStatus
CONFLICTING      # both agents appended at the same anchor
```

This is the honest result, and it is the *right* one. ScratchPost guarantees no
**semantic** collision; it does not pretend to resolve **textual** ones. Because
both agents appended at the same anchor, Git sees a hunk conflict — a loud,
visible failure instead of a silent one. `sp sync --rebase` surfaces it:

```console
$ sp sync --rebase --agent agent_2 --repo .
sp sync: rebase failed for case2: git rebase origin/main failed:
  error: could not apply 2182239... feat(payment): refunds (changeSet 201)
```

The conflict is a plain two-hunk overlap with **already-distinct ids**:

```diff
<<<<<<< HEAD
    <changeSet id="200" author="agent_1">
        <createTable tableName="oauth_tokens"/>
=======
    <changeSet id="201" author="agent_2">
        <createTable tableName="refunds"/>
>>>>>>> 2182239 (feat(payment): refunds (changeSet 201))
    </changeSet>
```

Resolving it is mechanical — keep both, in order — and the validator confirms:

```console
$ python3 scripts/validate-migrations.py
migration validation passed: all sequence numbers unique
```

PR #4 merged. `main`:

```console
$ git log --oneline -4
1d96daa Merge pull request #4 from saksham-sin/case2/agent-2-refunds
c05d769 feat(payment): refunds (changeSet 201)
e3cfe2b Merge pull request #3 from saksham-sin/case2/agent-1-oauth
6bd7f34 feat(auth): oauth_tokens (changeSet 200)

$ python3 scripts/validate-migrations.py
migration validation passed: all sequence numbers unique

$ grep -n 'changeSet id=' auth-service/src/main/resources/db/dbchangelog.xml
8:    <changeSet id="100" author="platform">
19:    <changeSet id="101" author="platform">
25:    <changeSet id="200" author="agent_1">
29:    <changeSet id="201" author="agent_2">
```

---

## 4. What actually changed

| Failure mode | Plain `git` | ScratchPost |
|---|---|---|
| `git checkout` tug-of-war | agent 1 silently on agent 2's branch | per-agent worktree, branch never shared |
| Uncommitted file overwrite | last writer wins | separate working trees |
| Port / cache collision on `mvn test` | both bind `8080` | `SP_PORT_BASE` band per session |
| Duplicate `changeSet id` | merges clean, breaks `main` | blocked pre-commit, agent renumbers |
| Duplicate Flyway `V200__` | merges clean, breaks `main` | blocked pre-commit |
| Conflicting PRs | both `MERGEABLE`, merged out of order | ordered by claim, merged in sequence |
| Who fixes it | a human, after `main` is red | the agent, in its own session |

The daemon does all of this deterministically — no LLM calls, no network, no
runtime beyond a single ~1 MB Rust binary. Measured idle RSS during this demo:
**3.8 MB**.

---

## 5. Reproduce it

```bash
# Case 1 — plain git
git clone https://github.com/saksham-sin/scratchpost-demo.git case1
cd case1
git checkout -b feat-auth-oauth      # agent 1
git checkout -b feat-payment-refund   # agent 2 — same folder, HEAD moves
# both insert changeSet id="200" at different anchors, merge both
python3 scripts/validate-migrations.py   # fails

# Case 2 — ScratchPost
git clone https://github.com/saksham-sin/scratchpost-demo.git case2
cd case2
sp init
sp run --agent agent_1 -- bash
sp run --agent agent_2 -- bash
# both insert changeSet id="200"; agent_1 commits, agent_2 is blocked
sp resequence --agent agent_2 --file ./auth-service/src/main/resources/db/dbchangelog.xml --from 200 --to 201
python3 scripts/validate-migrations.py   # passes
```

The broken Case 1 state is preserved on
[`case1-broken-main`](../../tree/case1-broken-main). `main` holds the Case 2
result.

---

## 6. Caveats

- **Textual conflicts are still textual.** ScratchPost prevents *semantic*
  collisions (duplicate sequence numbers, overlapping edits, stale bases). If two
  agents append at the same anchor, Git will still report a hunk conflict — but
  with distinct ids, so resolving it is mechanical rather than a judgement call.
- **The commit gate costs latency.** Roughly 100 ms per commit for the
  merge-tree and rule evaluation, against ~25 ms for a bare `git commit`.
- **No kernel-level sandboxing.** Sessions are isolated by worktree and
  environment, not by namespace or container. A determined agent can still write
  outside its workspace.
- **This demo is single-repo.** ScratchPost also handles multi-repo master
  folders; that path is exercised by the project's own `enterprise-sim.sh`.

---

<sub>Cat icon by [inmyheart](https://thenounproject.com/browse/icons/term/cat/) from Noun Project (CC BY 3.0).</sub>
