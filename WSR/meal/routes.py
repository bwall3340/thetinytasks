"""
Meal planner public blueprint — rolling 7-day view, no auth required.
"""
from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template

from .models import PlanEntry
from .claude import aggregate_ingredients

meal_bp = Blueprint('meal', __name__, url_prefix='/meal-planner')


def _rolling_week():
    """Build the 7-day rolling window starting today."""
    today = date.today()
    entries = []
    all_ingredients = []

    for i in range(7):
        d = today + timedelta(days=i)
        entry = PlanEntry.query.filter_by(date=d).first()
        recipe = entry.recipe if (entry and entry.recipe) else None

        if recipe and recipe.ingredients:
            all_ingredients.extend(recipe.ingredients)

        entries.append({
            'date': d,
            'date_display': d.strftime('%b %-d'),
            'day_name': d.strftime('%A'),
            'day_short': d.strftime('%a'),
            'is_today': i == 0,
            'recipe': recipe,
        })

    grocery = aggregate_ingredients(all_ingredients)
    return entries, grocery


@meal_bp.route('/')
def index():
    entries, grocery = _rolling_week()
    return render_template('meal/index.html', entries=entries, grocery=grocery)


@meal_bp.route('/api/week')
def api_week():
    entries, grocery = _rolling_week()
    return jsonify({
        'entries': [
            {
                'date': str(e['date']),
                'day_name': e['day_name'],
                'is_today': e['is_today'],
                'recipe': e['recipe'].to_dict() if e['recipe'] else None,
            }
            for e in entries
        ],
        'grocery': grocery,
    })
