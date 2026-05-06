"""
Meal planner — SQLAlchemy models.
Shares the same db instance and database as the market module.
"""
from datetime import datetime
from market.models import db


class Recipe(db.Model):
    __tablename__ = 'meal_recipes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    source_name = db.Column(db.String(200))       # e.g. "NYT Cooking", "Smitten Kitchen"
    source_url = db.Column(db.String(500))
    difficulty = db.Column(db.String(20))          # easy / medium / hard
    cuisine = db.Column(db.String(100))
    prep_minutes = db.Column(db.Integer)
    ingredients = db.Column(db.JSON)               # [{amount, unit, item, category}]
    instructions = db.Column(db.Text)
    tags = db.Column(db.JSON)                      # ["pasta", "weeknight", "easy"]
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan_entries = db.relationship('PlanEntry', back_populates='recipe')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source_name': self.source_name,
            'source_url': self.source_url,
            'difficulty': self.difficulty,
            'cuisine': self.cuisine,
            'prep_minutes': self.prep_minutes,
            'ingredients': self.ingredients or [],
            'instructions': self.instructions or '',
            'tags': self.tags or [],
            'active': self.active,
        }

    def summary_line(self):
        parts = [self.name]
        if self.difficulty:
            parts.append(self.difficulty)
        if self.cuisine:
            parts.append(self.cuisine)
        if self.tags:
            parts.append('tags: ' + ', '.join(self.tags))
        if self.prep_minutes:
            parts.append(f'{self.prep_minutes}min')
        return f'[{self.id}] ' + ' | '.join(parts)


class PlanEntry(db.Model):
    __tablename__ = 'meal_plan_entries'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('meal_recipes.id'), nullable=True)
    source = db.Column(db.String(20), default='admin')  # admin / auto
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recipe = db.relationship('Recipe', back_populates='plan_entries')


class Preference(db.Model):
    __tablename__ = 'meal_preferences'

    id = db.Column(db.Integer, primary_key=True)
    rule_text = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OrderHistory(db.Model):
    __tablename__ = 'meal_order_history'

    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.Date, nullable=True)          # extracted from invoice
    store = db.Column(db.String(100), default='Whole Foods')
    order_total = db.Column(db.Float, nullable=True)        # invoice grand total
    raw_text = db.Column(db.Text)
    parsed_items = db.Column(db.JSON)    # [{item, qty, unit, price, brand}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
