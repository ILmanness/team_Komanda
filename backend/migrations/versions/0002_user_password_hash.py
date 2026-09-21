"""Add password hash storage without inventing credentials for existing users."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('users', 'password_hash')
