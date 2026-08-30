"""
Meal planner admin — chat + recipe/plan management routes.

Mounted at /meal-planner/admin.  Authentication is handled centrally by
common.auth, so every route here simply carries @require_admin.
"""
import logging
from datetime import date, timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from common.auth import current_admin, require_admin
from market.models import db
from .models import Recipe, PlanEntry, Preference, OrderHistory

logger = logging.getLogger(__name__)

meal_admin_bp = Blueprint('meal_admin', __name__, url_prefix='/meal-planner/admin')


@meal_admin_bp.route('/')
@require_admin
def index():
    return redirect(url_for('meal_admin.dashboard'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@meal_admin_bp.route('/dashboard')
@require_admin
def dashboard():
    today = date.today()
    recipes = Recipe.query.filter_by(active=True).order_by(Recipe.name).all()
    preferences = Preference.query.filter_by(active=True).order_by(Preference.created_at).all()
    orders = OrderHistory.query.order_by(OrderHistory.order_date.desc().nullslast(),
                                         OrderHistory.created_at.desc()).all()

    # Next 7 days for the plan overview panel
    plan_days = []
    for i in range(7):
        d = today + timedelta(days=i)
        entry = PlanEntry.query.filter_by(date=d).first()
        plan_days.append({
            'date': d,
            'weekday': d.strftime('%a'),
            'is_today': i == 0,
            'recipe_name': entry.recipe.name if (entry and entry.recipe) else None,
            'entry_id': entry.id if entry else None,
        })

    return render_template(
        'meal_admin/dashboard.html',
        admin_user=current_admin(),
        recipes=recipes,
        preferences=preferences,
        plan_days=plan_days,
        orders=orders,
        recipe_count=len(recipes),
        pref_count=len(preferences),
        order_count=len(orders),
    )


# ── Chat API ──────────────────────────────────────────────────────────────────

@meal_admin_bp.route('/chat', methods=['POST'])
@require_admin
def chat():
    from .claude import chat_handler

    data = request.get_json() or {}
    messages = data.get('messages', [])
    if not messages:
        return jsonify({'error': 'No messages provided'}), 400

    today = date.today()
    recipes = Recipe.query.filter_by(active=True).order_by(Recipe.name).all()
    preferences = Preference.query.filter_by(active=True).order_by(Preference.created_at).all()

    # Build 14-day window (7 past + 7 future) for plan context
    plan_entries = []
    for i in range(-7, 8):
        d = today + timedelta(days=i)
        entry = PlanEntry.query.filter_by(date=d).first()
        plan_entries.append({
            'date': str(d),
            'weekday': d.strftime('%A'),
            'recipe_name': entry.recipe.name if (entry and entry.recipe) else None,
            'recipe_id': entry.recipe_id if entry else None,
        })

    context = {
        'today': str(today),
        'weekday': today.strftime('%A'),
        'recipe_count': len(recipes),
        'recipes': [
            {'summary': r.summary_line(), **r.to_dict()}
            for r in recipes
        ],
        'preferences': [{'id': p.id, 'rule_text': p.rule_text} for p in preferences],
        'plan_entries': plan_entries,
    }

    try:
        reply, tool_calls = chat_handler(messages, context)
        return jsonify({
            'reply': reply,
            'tool_calls': tool_calls,
            'refresh': len(tool_calls) > 0,
        })
    except Exception as e:
        logger.error('chat endpoint error: %s', e)
        return jsonify({'error': str(e)}), 500


# ── Recipe CRUD (direct form submissions from Recipes tab) ────────────────────

@meal_admin_bp.route('/recipes/<int:recipe_id>/delete', methods=['POST'])
@require_admin
def delete_recipe(recipe_id):
    recipe = db.session.get(Recipe, recipe_id)
    if recipe:
        recipe.active = False
        db.session.commit()
    return jsonify({'status': 'ok'})


# ── Plan management ────────────────────────────────────────────────────────────

@meal_admin_bp.route('/plan/clear', methods=['POST'])
@require_admin
def clear_plan_entry():
    data = request.get_json() or {}
    date_str = data.get('date')
    if not date_str:
        return jsonify({'error': 'date required'}), 400
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({'error': 'invalid date'}), 400
    entry = PlanEntry.query.filter_by(date=d).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
    return jsonify({'status': 'cleared'})


# ── Preference management ──────────────────────────────────────────────────────

@meal_admin_bp.route('/preferences/<int:pref_id>/delete', methods=['POST'])
@require_admin
def delete_preference(pref_id):
    pref = db.session.get(Preference, pref_id)
    if pref:
        pref.active = False
        db.session.commit()
    return jsonify({'status': 'ok'})


# ── Invoice upload (PDF → text extraction only, no Claude) ────────────────────

@meal_admin_bp.route('/invoice/upload', methods=['POST'])
@require_admin
def invoice_upload():
    import pdfplumber
    import io

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    try:
        pdf_bytes = file.read()
        pages_text = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = (page.extract_text() or '').strip()
                if text:
                    pages_text.append(text)

        if not pages_text:
            return jsonify({'error': 'Could not extract any text from this PDF'}), 400

        # Mark page boundaries so Claude can stitch split items
        full_text = '\n\n[PAGE BREAK]\n\n'.join(pages_text)
        return jsonify({'text': full_text, 'pages': len(pages_text)})

    except Exception as e:
        logger.error('Invoice PDF extraction error: %s', e)
        return jsonify({'error': f'Failed to read PDF: {e}'}), 500


# ── Order history management ───────────────────────────────────────────────────

@meal_admin_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@require_admin
def delete_order(order_id):
    order = db.session.get(OrderHistory, order_id)
    if order:
        db.session.delete(order)
        db.session.commit()
    return jsonify({'status': 'ok'})
