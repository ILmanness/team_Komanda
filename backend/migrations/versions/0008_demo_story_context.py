"""Provide the player with known facts in the existing demo scenes."""

from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE missions SET context=context || jsonb_build_object('public_context',
          'Приоритет и новый срок ещё не согласованы. Можно предложить выделить обязательный объём на ближайший релиз и обсудить перенос остальных задач. Какие задачи готовы и какие ресурсы доступны, уточните у Анны.')
        WHERE title='Демо · Первый разговор' AND mission_type='story'
          AND COALESCE(context->>'public_context', '')=''
    """)
    op.execute("""
        UPDATE missions SET context=context || jsonb_build_object('public_context',
          'Заказчик ожидает демонстрацию в пятницу. Готовность результата и возможный новый срок пока не подтверждены. Уточните, что можно показать в срок, и предложите согласовать дальнейший план.')
        WHERE title='Демо · Разговор с заказчиком' AND mission_type='story'
          AND COALESCE(context->>'public_context', '')=''
    """)


def downgrade():
    op.execute("""UPDATE missions SET context=context - 'public_context'
        WHERE title IN ('Демо · Первый разговор', 'Демо · Разговор с заказчиком')
          AND mission_type='story'""")
