"""Story unlocks are derived from successful sessions, never from client state."""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection


def get_story_progress(connection: Connection, storyline_id: UUID, user_id: UUID) -> list[dict]:
    missions = connection.execute(text('''
        SELECT id, branch_key, order_index
        FROM missions
        WHERE storyline_id = :storyline_id AND mission_type = 'story' AND status = 'published'
        ORDER BY branch_key, order_index, id
    '''), {'storyline_id': storyline_id}).mappings().all()
    completed = set(connection.execute(text('''
        SELECT p.mission_id
        FROM story_mission_progress AS p
        JOIN missions AS m ON m.id = p.mission_id
        WHERE p.user_id = :user_id AND m.storyline_id = :storyline_id
    '''), {'user_id': user_id, 'storyline_id': storyline_id}).scalars())
    branch_open: dict[str, bool] = {}
    result = []
    for mission in missions:
        branch = mission['branch_key']
        unlocked = branch_open.get(branch, True)
        success = mission['id'] in completed
        result.append({'mission_id': mission['id'], 'unlocked': unlocked, 'completed': success})
        branch_open[branch] = unlocked and success
    return result
