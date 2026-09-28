# ADR-0001: SQLite Is Authoritative Metadata

## Decision

SQLite is the authoritative local metadata store. It remains transactional,
portable, inspectable, serverless, and suitable for temporal, full-text, and
spatial indexes. Large bytes are stored outside the database by hash.

## Consequence

The project can be opened and inspected without a hosted service. Database
schema changes must be versioned and verified before a project is exported.

