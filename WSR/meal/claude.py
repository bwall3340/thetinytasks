"""
Meal planner — Claude API integration.
Handles the agentic chat interface and nightly recipe auto-selection.
"""
import json
import logging
import os
import re
from collections import defaultdict
from datetime import date as _date, timedelta
from fractions import Fraction

import anthropic

logger = logging.getLogger(__name__)

# ── JSON extraction (same pattern as market/analyzer.py) ─────────────────────

def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── Ingredient aggregation ───────────────────────────────────────────────────

# Interchangeable/similar ingredients → canonical grocery item
_INGREDIENT_ALIASES: dict[str, str] = {
    # dairy interchangeables
    'half and half': 'heavy cream',
    'heavy whipping cream': 'heavy cream',
    'whipping cream': 'heavy cream',
    'double cream': 'heavy cream',
    # butter variants
    'salted butter': 'butter',
    'unsalted butter': 'butter',
    'sweet cream butter': 'butter',
    # lemon forms
    'lemon juice': 'lemon',
    'fresh lemon juice': 'lemon',
    'juice of 1 lemon': 'lemon',
    'juice of lemon': 'lemon',
    'small lemon': 'lemon',
    'lemons': 'lemon',
    # lime forms
    'lime juice': 'lime',
    'fresh lime juice': 'lime',
    'limes': 'lime',
    # onion family
    'green onion': 'scallion',
    'green onions': 'scallion',
    'scallions': 'scallion',
    'spring onion': 'scallion',
    'spring onions': 'scallion',
}

# Spices shown without quantity when total is under a jar's worth
_SPICE_NAMES: frozenset[str] = frozenset({
    'paprika', 'smoked paprika', 'sweet paprika',
    'cumin', 'coriander', 'turmeric', 'cinnamon',
    'oregano', 'dried oregano', 'thyme', 'dried thyme',
    'rosemary', 'dried rosemary', 'basil', 'dried basil',
    'sage', 'dried sage', 'dill', 'dried dill',
    'cayenne', 'cayenne pepper', 'chili powder',
    'garlic powder', 'onion powder',
    'ginger', 'ground ginger', 'nutmeg', 'allspice',
    'cloves', 'cardamom', 'fennel seeds',
    'black pepper', 'white pepper', 'pepper',
    'red pepper flakes', 'crushed red pepper',
    'bay leaf', 'bay leaves',
    'mustard powder', 'mustard seeds',
    'curry powder', 'garam masala',
    'italian seasoning', 'herbs de provence',
    "za'atar", 'zaatar', 'chinese five spice', 'five spice',
    'ancho chili', 'chipotle powder',
    'salt', 'kosher salt', 'sea salt', 'flaky salt',
})

_UNIT_TO_TSP: dict[str, float] = {
    'tsp': 1, 'teaspoon': 1, 'teaspoons': 1,
    'tbsp': 3, 'tablespoon': 3, 'tablespoons': 3, 't': 3,
    'cup': 48, 'cups': 48,
}
_SPICE_TSP_LIMIT = 9  # ≤ 3 tbsp → a standard jar covers it, omit quantity


def aggregate_ingredients(all_ingredients: list) -> dict:
    """
    Aggregate a flat list of ingredient dicts into a category-grouped dict.
    Input:  [{amount, unit, item, category}, ...]
    Output: {category: [{item, combined}, ...], ...}

    Smart combining: aliases map similar items to one canonical entry;
    missing amounts default to 1; spices under _SPICE_TSP_LIMIT show name only.
    """
    groups = defaultdict(lambda: {'amounts': [], 'unit': '', 'item': '', 'category': 'other'})

    for ing in all_ingredients:
        raw_item = (ing.get('item') or '').strip()
        if not raw_item:
            continue

        item_lower = raw_item.lower()
        canonical = _INGREDIENT_ALIASES.get(item_lower, item_lower)
        unit_key = (ing.get('unit') or '').lower().strip()
        key = (canonical, unit_key)

        # Default missing amount to 1 so items always have a countable quantity
        raw_amount = str(ing.get('amount') or '').strip()
        amount_val = raw_amount if raw_amount else '1'

        groups[key]['amounts'].append(amount_val)
        groups[key]['unit'] = ing.get('unit') or ''
        # Display name: alias or original, always capitalize first letter
        alias = _INGREDIENT_ALIASES.get(item_lower)
        display = alias if alias else raw_item
        groups[key]['item'] = display[0].upper() + display[1:] if display else display
        groups[key]['category'] = (ing.get('category') or 'other').lower()

    category_order = ['produce', 'proteins', 'dairy', 'grains', 'pantry', 'other']
    result = {}

    for cat in category_order:
        cat_items = []
        for (item_key, unit_key), data in groups.items():
            if data['category'] != cat:
                continue

            display_item = data['item']
            amounts = data['amounts']

            try:
                parsed = []
                for a in amounts:
                    parts = a.strip().split()
                    if len(parts) == 2:
                        parsed.append(Fraction(int(parts[0])) + Fraction(parts[1]))
                    else:
                        parsed.append(Fraction(a))
                total = sum(parsed) if parsed else Fraction(0)

                # Spices: omit quantity when total fits in a standard jar
                if display_item.lower() in _SPICE_NAMES:
                    tsp_mult = _UNIT_TO_TSP.get(unit_key, 1)
                    if float(total) * tsp_mult <= _SPICE_TSP_LIMIT:
                        cat_items.append({'item': display_item, 'combined': display_item})
                        continue

                if total.denominator == 1:
                    amount_str = str(total.numerator)
                else:
                    whole = total.numerator // total.denominator
                    rem = total - whole
                    amount_str = f'{whole} {rem}' if whole else str(total)

            except (ValueError, ZeroDivisionError):
                # Unparseable amount (e.g. "to taste") — spices still drop quantity
                if display_item.lower() in _SPICE_NAMES:
                    cat_items.append({'item': display_item, 'combined': display_item})
                    continue
                amount_str = ', '.join(a for a in amounts if a)

            parts = [p for p in [amount_str, data['unit'], display_item] if p]
            cat_items.append({'item': display_item, 'combined': ' '.join(parts)})

        if cat_items:
            result[cat] = sorted(cat_items, key=lambda x: x['item'].lower())

    return result


# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    {
        'name': 'get_recipes',
        'description': 'Get all active recipes in the library.',
        'input_schema': {'type': 'object', 'properties': {}, 'required': []},
    },
    {
        'name': 'get_preferences',
        'description': 'Get all active preference/constraint rules.',
        'input_schema': {'type': 'object', 'properties': {}, 'required': []},
    },
    {
        'name': 'get_plan_window',
        'description': 'Get meal plan entries for a date range.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'start_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
                'days': {'type': 'integer', 'description': 'Number of days (default 7)'},
            },
            'required': ['start_date'],
        },
    },
    {
        'name': 'add_recipe',
        'description': 'Add a new recipe to the library.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'source_name': {'type': 'string'},
                'source_url': {'type': 'string'},
                'difficulty': {'type': 'string', 'enum': ['easy', 'medium', 'hard']},
                'cuisine': {'type': 'string'},
                'prep_minutes': {'type': 'integer'},
                'ingredients': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'amount': {'type': 'string'},
                            'unit': {'type': 'string'},
                            'item': {'type': 'string'},
                            'category': {
                                'type': 'string',
                                'enum': ['produce', 'proteins', 'dairy', 'grains', 'pantry', 'other'],
                            },
                        },
                        'required': ['item'],
                    },
                },
                'instructions': {'type': 'string'},
                'tags': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['name', 'ingredients', 'instructions'],
        },
    },
    {
        'name': 'update_recipe',
        'description': 'Update fields on an existing recipe.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'recipe_id': {'type': 'integer'},
                'name': {'type': 'string'},
                'source_name': {'type': 'string'},
                'source_url': {'type': 'string'},
                'difficulty': {'type': 'string'},
                'cuisine': {'type': 'string'},
                'prep_minutes': {'type': 'integer'},
                'ingredients': {'type': 'array'},
                'instructions': {'type': 'string'},
                'tags': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['recipe_id'],
        },
    },
    {
        'name': 'deactivate_recipe',
        'description': 'Soft-delete a recipe (removes it from future plans).',
        'input_schema': {
            'type': 'object',
            'properties': {'recipe_id': {'type': 'integer'}},
            'required': ['recipe_id'],
        },
    },
    {
        'name': 'save_preference',
        'description': 'Save a new meal planning preference rule.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'rule_text': {
                    'type': 'string',
                    'description': 'Plain English rule, e.g. "No pasta more than once per week"',
                },
            },
            'required': ['rule_text'],
        },
    },
    {
        'name': 'deactivate_preference',
        'description': 'Remove an active preference rule.',
        'input_schema': {
            'type': 'object',
            'properties': {'preference_id': {'type': 'integer'}},
            'required': ['preference_id'],
        },
    },
    {
        'name': 'set_plan_entry',
        'description': 'Assign a recipe to a specific calendar date.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'date': {'type': 'string', 'description': 'YYYY-MM-DD'},
                'recipe_id': {'type': 'integer'},
            },
            'required': ['date', 'recipe_id'],
        },
    },
    {
        'name': 'clear_plan_entry',
        'description': 'Remove the recipe assignment from a specific date.',
        'input_schema': {
            'type': 'object',
            'properties': {'date': {'type': 'string', 'description': 'YYYY-MM-DD'}},
            'required': ['date'],
        },
    },
    {
        'name': 'get_grocery_list',
        'description': 'Get the aggregated grocery list for a date range.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'start_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
                'days': {'type': 'integer', 'description': 'Number of days (default 7)'},
            },
            'required': ['start_date'],
        },
    },
    {
        'name': 'save_order_history',
        'description': (
            'Save a confirmed grocery invoice to order history with price data. '
            'ALWAYS show the user a full item list and ask for confirmation before calling this tool.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'order_date': {'type': 'string', 'description': 'Order date as YYYY-MM-DD'},
                'store': {'type': 'string', 'description': 'Store name (default: Whole Foods)'},
                'order_total': {'type': 'number', 'description': 'Invoice grand total in dollars'},
                'raw_text': {'type': 'string', 'description': 'Full invoice text for the record'},
                'parsed_items': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'item': {'type': 'string', 'description': 'Product name'},
                            'qty': {'type': 'string', 'description': 'Quantity (e.g. "2", "1 lb")'},
                            'unit': {'type': 'string', 'description': 'Unit if separate from qty'},
                            'price': {'type': 'number', 'description': 'Total price for this line item'},
                            'brand': {'type': 'string', 'description': 'Brand name if shown'},
                        },
                        'required': ['item', 'price'],
                    },
                },
            },
            'required': ['order_date', 'raw_text', 'parsed_items'],
        },
    },
    {
        'name': 'scrape_recipe_url',
        'description': (
            'Fetch a recipe URL and return the page text so you can parse it into add_recipe. '
            'If scraping fails (blocked, paywall, timeout), return the error so the user knows '
            'to paste the recipe text manually instead.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'url': {'type': 'string', 'description': 'Full URL of the recipe page'}},
            'required': ['url'],
        },
    },
]


# ── URL scraper ───────────────────────────────────────────────────────────────

def _scrape_url(url: str) -> dict:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return {'error': 'Scraping dependencies not available — paste the recipe text instead.'}

    try:
        resp = requests.get(
            url, timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; recipe-parser/1.0)'},
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return {'error': 'Request timed out — the site may be slow or blocking scrapers. Paste the recipe text instead.'}
    except requests.exceptions.RequestException as e:
        return {'error': f'Could not reach the URL ({e}). Paste the recipe text instead.'}

    if resp.status_code == 403:
        return {'error': 'Site blocked the request (403 Forbidden) — likely a paywall or bot protection. Paste the recipe text instead.'}
    if resp.status_code == 401:
        return {'error': 'Site requires login (401) — paste the recipe text instead.'}
    if resp.status_code != 200:
        return {'error': f'Site returned HTTP {resp.status_code} — paste the recipe text instead.'}

    soup = BeautifulSoup(resp.text, 'lxml')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
        tag.decompose()

    text = soup.get_text(' ', strip=True)
    if len(text) < 100:
        return {'error': 'Page returned very little text — likely a paywall or JS-rendered site. Paste the recipe text instead.'}

    return {'text': text[:8000], 'url': url}


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_tool(name: str, inp: dict) -> dict:
    """Execute a tool call within the current Flask/SQLAlchemy app context."""
    from .models import Recipe, PlanEntry, Preference, OrderHistory
    from market.models import db

    if name == 'get_recipes':
        recipes = Recipe.query.filter_by(active=True).order_by(Recipe.name).all()
        return [r.to_dict() for r in recipes]

    if name == 'get_preferences':
        prefs = Preference.query.filter_by(active=True).order_by(Preference.created_at).all()
        return [{'id': p.id, 'rule_text': p.rule_text} for p in prefs]

    if name == 'get_plan_window':
        start = _date.fromisoformat(inp['start_date'])
        days = inp.get('days', 7)
        result = {}
        for i in range(days):
            d = start + timedelta(days=i)
            entry = PlanEntry.query.filter_by(date=d).first()
            result[str(d)] = entry.recipe.to_dict() if (entry and entry.recipe) else None
        return result

    if name == 'add_recipe':
        recipe = Recipe(
            name=inp['name'],
            source_name=inp.get('source_name'),
            source_url=inp.get('source_url'),
            difficulty=inp.get('difficulty'),
            cuisine=inp.get('cuisine'),
            prep_minutes=inp.get('prep_minutes'),
            ingredients=inp.get('ingredients', []),
            instructions=inp.get('instructions', ''),
            tags=inp.get('tags', []),
        )
        db.session.add(recipe)
        db.session.commit()
        return {'status': 'saved', 'recipe_id': recipe.id}

    if name == 'update_recipe':
        recipe = db.session.get(Recipe, inp['recipe_id'])
        if not recipe:
            return {'error': 'Recipe not found'}
        for field in ('name', 'source_name', 'source_url', 'difficulty', 'cuisine',
                      'prep_minutes', 'ingredients', 'instructions', 'tags'):
            if field in inp:
                setattr(recipe, field, inp[field])
        db.session.commit()
        return {'status': 'updated', 'recipe_id': recipe.id}

    if name == 'deactivate_recipe':
        recipe = db.session.get(Recipe, inp['recipe_id'])
        if not recipe:
            return {'error': 'Recipe not found'}
        recipe.active = False
        db.session.commit()
        return {'status': 'deactivated', 'recipe_id': recipe.id}

    if name == 'save_preference':
        pref = Preference(rule_text=inp['rule_text'])
        db.session.add(pref)
        db.session.commit()
        return {'status': 'saved', 'preference_id': pref.id}

    if name == 'deactivate_preference':
        pref = db.session.get(Preference, inp['preference_id'])
        if not pref:
            return {'error': 'Preference not found'}
        pref.active = False
        db.session.commit()
        return {'status': 'deactivated'}

    if name == 'set_plan_entry':
        d = _date.fromisoformat(inp['date'])
        recipe = db.session.get(Recipe, inp['recipe_id'])
        if not recipe:
            return {'error': 'Recipe not found'}
        entry = PlanEntry.query.filter_by(date=d).first()
        if entry:
            entry.recipe_id = recipe.id
            entry.source = 'admin'
        else:
            entry = PlanEntry(date=d, recipe_id=recipe.id, source='admin')
            db.session.add(entry)
        db.session.commit()
        return {'status': 'set', 'date': str(d), 'recipe': recipe.name}

    if name == 'clear_plan_entry':
        d = _date.fromisoformat(inp['date'])
        entry = PlanEntry.query.filter_by(date=d).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
        return {'status': 'cleared', 'date': str(d)}

    if name == 'get_grocery_list':
        start = _date.fromisoformat(inp['start_date'])
        days = inp.get('days', 7)
        all_ingredients = []
        for i in range(days):
            d = start + timedelta(days=i)
            entry = PlanEntry.query.filter_by(date=d).first()
            if entry and entry.recipe and entry.recipe.ingredients:
                all_ingredients.extend(entry.recipe.ingredients)
        return aggregate_ingredients(all_ingredients)

    if name == 'save_order_history':
        order_date = None
        if inp.get('order_date'):
            try:
                from datetime import date as _date_cls
                order_date = _date_cls.fromisoformat(inp['order_date'])
            except ValueError:
                pass
        history = OrderHistory(
            order_date=order_date,
            store=inp.get('store', 'Whole Foods'),
            order_total=inp.get('order_total'),
            raw_text=inp['raw_text'],
            parsed_items=inp.get('parsed_items', []),
        )
        db.session.add(history)
        db.session.commit()
        item_count = len(history.parsed_items or [])
        return {'status': 'saved', 'order_id': history.id, 'items_saved': item_count}

    if name == 'scrape_recipe_url':
        return _scrape_url(inp['url'])

    return {'error': f'Unknown tool: {name}'}


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system(context: dict) -> str:
    today = context['today']
    weekday = context['weekday']

    recipe_lines = '\n'.join(r['summary'] for r in context['recipes']) or 'No recipes yet.'
    pref_lines = '\n'.join(f'[{p["id"]}] {p["rule_text"]}' for p in context['preferences']) or 'None set.'
    plan_lines = '\n'.join(
        f'{e["date"]} ({e["weekday"]}): {e["recipe_name"] or "TBD"}'
        for e in context['plan_entries']
    )

    return f"""You are a personal meal planning assistant. Today is {today} ({weekday}).

RECIPE LIBRARY ({context['recipe_count']} recipes):
{recipe_lines}

ACTIVE PREFERENCE RULES:
{pref_lines}

MEAL PLAN (past 7 days + next 7 days):
{plan_lines}

---
Use your tools to:
- Add/update/remove recipes (when the user pastes recipe text, parse it into structured fields)
- Set/manage preference rules
- Assign recipes to calendar dates to build the weekly plan
- Generate grocery lists from planned recipes
- Parse and save grocery invoices to order history

When the user pastes a recipe, confirm what you parsed before saving.
When assigning meals for multiple days, respect all active preference rules and avoid repeating recipes served in the past 14 days unless necessary.
Format dates as YYYY-MM-DD when calling tools. Be concise.

INVOICE PARSING — follow this exact process:
1. The user will share invoice text, possibly containing [PAGE BREAK] markers between pages.
   IMPORTANT: Items can be split across page breaks — the product name may appear at the bottom
   of one page while its quantity and price appear at the top of the next. Always read across
   page breaks before assuming a line is complete.
2. Extract: order date, store name, every line item (name, qty, price), and the grand total.
   Skip non-product lines (delivery fees, tips, taxes — include tax in order_total only).
3. Before calling save_order_history, show a confirmation in this format:
   "Order date: [date] | [store] | [N] items | Total: $[X.XX]
   1. [item] — qty: [q] — $[price]
   2. ..."
4. End with: "Does this look correct? Reply 'save it' to confirm, or tell me what to fix."
5. Only call save_order_history after the user explicitly confirms. Never save speculatively."""


# ── Chat handler ──────────────────────────────────────────────────────────────

def chat_handler(messages: list, context: dict) -> tuple[str, list]:
    """
    Run the agentic chat loop with tool use.
    messages: [{role, content}] — content is always a plain string from the frontend
    Returns: (reply_text, list_of_tool_names_called)
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return 'ANTHROPIC_API_KEY is not configured.', []

    client = anthropic.Anthropic(api_key=api_key)
    system = _build_system(context)
    api_messages = [{'role': m['role'], 'content': m['content']} for m in messages]
    tool_calls_made = []

    for _ in range(15):
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=api_messages,
        )

        if response.stop_reason == 'end_turn':
            text = next((b.text for b in response.content if hasattr(b, 'text')), '')
            return text, tool_calls_made

        if response.stop_reason == 'tool_use':
            tool_results = []
            for block in response.content:
                if block.type == 'tool_use':
                    result = _execute_tool(block.name, block.input)
                    tool_calls_made.append(block.name)
                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': block.id,
                        'content': json.dumps(result),
                    })
            api_messages.append({'role': 'assistant', 'content': response.content})
            api_messages.append({'role': 'user', 'content': tool_results})
        else:
            break

    return 'Something went wrong — please try again.', tool_calls_made


# ── Nightly auto-pick ─────────────────────────────────────────────────────────

def auto_pick_recipe(target_date, recipes, preferences, recent_entries) -> int | None:
    """
    Ask Claude to pick a recipe_id for target_date given the library and constraints.
    Called by the nightly scheduler outside of a request context.
    """
    if not recipes:
        return None

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    recipe_lines = '\n'.join(r.summary_line() for r in recipes)
    rules_text = '\n'.join(f'- {p.rule_text}' for p in preferences) or 'None.'
    history_lines = '\n'.join(
        f'{e.date}: {e.recipe.name} [{e.recipe_id}]'
        for e in recent_entries if e.recipe
    ) or 'None.'
    day_name = target_date.strftime('%A')

    prompt = f"""Pick one dinner recipe for {day_name}, {target_date}.

AVAILABLE RECIPES:
{recipe_lines}

PREFERENCE RULES (must follow):
{rules_text}

RECENTLY SERVED (avoid repeating too soon):
{history_lines}

Return ONLY valid JSON: {{"recipe_id": <integer>, "reason": "<one sentence>"}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}],
        )
        data = _extract_json(message.content[0].text)
        if data and isinstance(data, dict) and 'recipe_id' in data:
            return int(data['recipe_id'])
    except Exception as e:
        logger.error('auto_pick_recipe error for %s: %s', target_date, e)

    return None
