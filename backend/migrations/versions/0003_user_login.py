"""Give every user a unique login; preserve existing email sign-in."""
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE users ADD COLUMN login varchar(40)')
    op.execute("UPDATE users SET login = 'user-' || replace(id::text, '-', '')")
    op.execute("ALTER TABLE users ALTER COLUMN login SET DEFAULT ('user-' || replace(gen_random_uuid()::text, '-', ''))")
    op.execute('ALTER TABLE users ALTER COLUMN login SET NOT NULL')
    op.execute('CREATE UNIQUE INDEX ix_users_login_lower ON users (lower(login))')


def downgrade():
    op.execute('DROP INDEX ix_users_login_lower')
    op.execute('ALTER TABLE users DROP COLUMN login')
