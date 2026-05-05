"""
Nightly meal plan auto-fill.
Runs at midnight UTC — fills any gaps in the next 7 days using Claude + preference rules.
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def run_meal_auto_fill(app):
    from .models import Recipe, PlanEntry, Preference
    from .claude import auto_pick_recipe
    from market.models import db

    with app.app_context():
        recipes = Recipe.query.filter_by(active=True).all()
        preferences = Preference.query.filter_by(active=True).all()

        if not recipes:
            logger.info('Meal auto-fill: no recipes in library, skipping')
            return

        today = date.today()

        for i in range(1, 8):
            target = today + timedelta(days=i)
            entry = PlanEntry.query.filter_by(date=target).first()

            if entry and entry.recipe_id:
                continue  # already assigned

            recent = PlanEntry.query.filter(
                PlanEntry.date >= today - timedelta(days=14),
                PlanEntry.date < target,
                PlanEntry.recipe_id.isnot(None),
            ).all()

            recipe_id = auto_pick_recipe(target, recipes, preferences, recent)

            if recipe_id:
                if entry:
                    entry.recipe_id = recipe_id
                    entry.source = 'auto'
                else:
                    entry = PlanEntry(date=target, recipe_id=recipe_id, source='auto')
                    db.session.add(entry)
                db.session.commit()
                logger.info('Meal auto-fill: %s → recipe %s', target, recipe_id)
            else:
                logger.warning('Meal auto-fill: could not pick recipe for %s', target)
