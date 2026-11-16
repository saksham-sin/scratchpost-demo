CREATE TABLE payments (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    amount_cents BIGINT NOT NULL,
    currency    VARCHAR(3) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
