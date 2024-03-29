DROP TABLE IF EXISTS Blocks;
DROP TABLE IF EXISTS Trx;
DROP TABLE IF EXISTS Coins;
CREATE TABLE IF NOT EXISTS Blocks (
    hash VARCHAR(64) NOT NULL PRIMARY KEY,
    height BIGINT NOT NULL,
    nonce BIGINT,
    number_trx BIGINT,
    merkle_root VARCHAR(64),
    previous_hash VARCHAR(64),
    time DATETIME
);
CREATE TABLE IF NOT EXISTS Trx (
    hash VARCHAR(64) NOT NULL PRIMARY KEY,
    include_block VARCHAR(64) NOT NULL,
    value BIGINT,
    t_index BIGINT NOT NULL,
    time DATETIME
);
CREATE TABLE IF NOT EXISTS Coins (
    hash VARCHAR(64) NOT NULL PRIMARY KEY,
    created_trx_hash VARCHAR(64) NOT NULL,
    out_index BIGINT NOT NULL,
    value BIGINT NOT NULL,
    owner VARCHAR(64) NOT NULL,
    trx_hash VARCHAR(64),
    in_index BIGINT
);
