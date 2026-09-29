"""Record revoked JWTs until their normal expiry."""

from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE revoked_access_tokens (
        token_hash CHAR(64) PRIMARY KEY,
        expires_at TIMESTAMPTZ NOT NULL
    )''')
    op.execute('CREATE INDEX ix_revoked_access_tokens_expires_at ON revoked_access_tokens (expires_at)')


def downgrade():
    op.execute('DROP TABLE revoked_access_tokens')
