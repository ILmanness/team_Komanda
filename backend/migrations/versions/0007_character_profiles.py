"""Give authored characters public portraits and PAEI behavior profiles."""

from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE characters ADD COLUMN paei_profile_id uuid REFERENCES paei_profiles(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE characters ADD COLUMN paei_description text NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE characters ADD COLUMN behavior_description text NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE characters ADD COLUMN portrait_url text NOT NULL DEFAULT ''")
    op.execute("""
        INSERT INTO paei_profiles(code, leading_letter, p_value, a_value, e_value, i_value, prompt_rules)
        VALUES
          ('DEMO_A', 'A', 45, 85, 35, 55, 'Ценит ясный план, ответственность и предсказуемые сроки.'),
          ('DEMO_I', 'I', 45, 50, 35, 85, 'Сначала помогает понять другого человека, затем предлагает решение.')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        UPDATE characters SET
          paei_profile_id=(SELECT id FROM paei_profiles WHERE code='DEMO_A'),
          paei_description='A · Администратор. Анна выстраивает порядок: ей нужны ясные сроки, ответственные и видимый план.',
          behavior_description='Сначала уточняет факты и риск для команды. Становится теплее, когда собеседник признаёт проблему и предлагает конкретный следующий шаг.',
          portrait_url='/images/anna-frames.png',
          description=CASE WHEN description='Спокойно уточняет причины задержки.' THEN
            'Руководитель проекта. Держит в голове сроки всей команды и не любит сюрпризы перед релизом.' ELSE description END
        WHERE slug='demo-anna'
    """)
    op.execute("""
        UPDATE characters SET
          paei_profile_id=(SELECT id FROM paei_profiles WHERE code='DEMO_P'),
          paei_description='P · Производитель результата. Игорь смотрит на договорённости через итог и срок: ему важно, что будет сделано.',
          behavior_description='Задаёт прямые вопросы о результате. Недоверчив к общим обещаниям, но готов обсуждать честный план с контрольными точками.',
          portrait_url='/images/igor-frames.png',
          description=CASE WHEN description='Ценит конкретные сроки и прозрачность.' THEN
            'Заказчик проекта. Ждёт обещанный результат и хочет понимать, что изменится после трудного разговора.' ELSE description END
        WHERE slug='demo-igor'
    """)
    op.execute("""
        UPDATE characters SET
          paei_profile_id=(SELECT id FROM paei_profiles WHERE code='DEMO_I'),
          paei_description='I · Интегратор. Наставница помогает увидеть интересы людей и сохранить рабочие отношения.',
          behavior_description='Не оценивает через нейросеть. Описывает ситуацию, показывает последствия выбранного варианта и объясняет подготовленную подсказку.',
          portrait_url='/images/mentor-frames.png',
          description='Опытная коллега, которая ведёт тренировки. Помогает разобрать решение без давления и вернуться к материалу.'
        WHERE slug='training-mentor'
    """)


def downgrade():
    op.execute('ALTER TABLE characters DROP COLUMN portrait_url')
    op.execute('ALTER TABLE characters DROP COLUMN behavior_description')
    op.execute('ALTER TABLE characters DROP COLUMN paei_description')
    op.execute('ALTER TABLE characters DROP COLUMN paei_profile_id')
