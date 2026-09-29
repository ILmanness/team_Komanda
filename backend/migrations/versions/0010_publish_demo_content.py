"""Publish the bundled demo scenario after the editorial import retired it."""

from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE storylines SET status='published' WHERE slug='demo-first-week'")
    op.execute("UPDATE knowledge_items SET status='published' WHERE slug='demo-negotiation'")
    op.execute("""
        UPDATE missions SET status='published'
        WHERE storyline_id=(SELECT id FROM storylines WHERE slug='demo-first-week')
           OR title='Демо · Сорванный срок'
    """)


def downgrade():
    # Do not unexpectedly hide content after users have started these missions.
    pass
