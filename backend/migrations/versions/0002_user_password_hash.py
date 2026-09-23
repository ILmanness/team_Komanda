"""Add password hash storage without inventing credentials for existing users."""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # The users/catalog branch also shipped this column inside revision 0001.
    # Support databases created from either branch without losing existing hashes.
    op.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT')
    op.execute('ALTER TABLE users ALTER COLUMN password_hash TYPE TEXT')


def downgrade():
    op.drop_column('users', 'password_hash')
