# backend/services/achievement_service.py

import operator as op
import logging
from typing import List, Union, Optional

from backend import models

logger = logging.getLogger(__name__)

# Operator mapping for criteria evaluation
OPERATORS = {
    '>': op.gt,
    '<': op.lt,
    '>=': op.ge,
    '<=': op.le,
    '==': op.eq,
    '!=': op.ne,
}

def get_current_value_for_achievement(
    achievement: models.Achievement,
    stats: Union[models.UserStats, List[models.UserStats]]
) -> Optional[Union[int, float]]:
    """
    Calculates the current value a user has for a given achievement's criteria.
    This is used to show progress towards an achievement.
    """
    criteria = achievement.criteria
    if not isinstance(criteria, dict):
        return None

    stat_name = criteria.get('stat')
    if not stat_name:
        return None

    actual_value = None
    if achievement.type == models.AchievementType.GLOBAL:
        if not isinstance(stats, list):
            logger.error(f"Global achievement '{achievement.key}' check requires a list of stats, got {type(stats)}.")
            return None
        
        agg_method = criteria.get('agg_method')
        if agg_method == 'sum':
            actual_value = sum(getattr(s, stat_name, 0) or 0 for s in stats)
        elif agg_method == 'count':
            actual_value = len(stats)
        elif agg_method == 'max':
            # Find the max value of the stat across all of the user's feed stats records
            actual_value = max((getattr(s, stat_name, 0) or 0 for s in stats), default=0)
        else:
            logger.warning(f"Unsupported or missing agg_method for GLOBAL achievement '{achievement.key}'.")
            return None

    else:  # PER_FEED
        if not isinstance(stats, models.UserStats):
            logger.error(f"Per-feed achievement '{achievement.key}' check requires a single UserStats object, got {type(stats)}.")
            return None
        actual_value = getattr(stats, stat_name, None)

    return actual_value

def check_achievement_criteria(
    achievement: models.Achievement,
    stats: Union[models.UserStats, List[models.UserStats]]
) -> bool:
    """
    Checks if a user's stats meet the criteria for a given achievement.
    """
    criteria = achievement.criteria
    if not isinstance(criteria, dict):
        logger.warning(f"Achievement '{achievement.key}' has no criteria or it's not a dict.")
        return False

    operator_str = criteria.get('operator')
    required_value = criteria.get('value')
    if not all([operator_str, required_value is not None]):
        logger.warning(f"Achievement '{achievement.key}' has invalid criteria (missing operator or value): {criteria}")
        return False

    operator_func = OPERATORS.get(operator_str)
    if not operator_func:
        logger.warning(f"Unsupported operator '{operator_str}' in achievement '{achievement.key}'.")
        return False

    actual_value = get_current_value_for_achievement(achievement, stats)
    if actual_value is None:
        return False

    return operator_func(actual_value, required_value)