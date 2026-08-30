"""
Image slot registry — the single source of truth for every managed image.

A "slot" is a named position on a public page (the hero, a tool card, the
philosophy panel...).  Each slot maps to a stable public filename under
/assets/, which is what the static HTML and CSS request.  Whether that
filename resolves to a Sanity CDN image or the committed fallback file is
decided at request time by the /assets/<filename> route — so the markup never
has to change when an image is swapped in the admin.

Adding a new managed image = add one Slot here, reference its `filename` in
the markup, and it appears in the admin automatically.
"""
from collections import OrderedDict

# Accepted upload types, mapped to the extension Sanity should store.
ALLOWED_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
}

# Per-file upload ceiling. Flask's MAX_CONTENT_LENGTH (16MB) is the hard stop;
# this is the friendlier limit enforced at the route boundary.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class Slot:
    """One managed image position on a public page."""

    def __init__(self, slot_id, label, filename, aspect, group, hint):
        self.id = slot_id
        self.label = label
        self.filename = filename      # public path segment under /assets/
        self.aspect = aspect          # CSS aspect-ratio the slot renders at
        self.group = group            # admin UI grouping
        self.hint = hint              # guidance shown in the admin

    @property
    def public_url(self):
        return '/assets/' + self.filename

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'filename': self.filename,
            'aspect': self.aspect,
            'group': self.group,
            'hint': self.hint,
            'public_url': self.public_url,
        }


# Order here is the order shown in the admin dashboard.
_SLOTS = [
    Slot('hero', 'Hero background', 'hero.jpg', '2 / 1', 'Home page',
         'Full-bleed cover image. Wide and cinematic — a dark overlay sits on '
         'top, so mid-tone images read best. 2400×1200 or larger.'),

    Slot('sankey-chart', 'Sankey Chart card', 'sankey-card.jpg', '16 / 10', 'Tool cards',
         'Card image for the Sankey Chart tool. 1600×1000.'),

    Slot('background-remover', 'Background Remover card', 'backgroundRemoval-card.jpg', '16 / 10', 'Tool cards',
         'Card image for Background Remover Pro. 1600×1000.'),

    Slot('return-stream', 'Return Stream card', 'returnstream-card.png', '16 / 10', 'Tool cards',
         'Card image for the Return Stream Digitizer. 1600×1000.'),

    Slot('market-outlook', 'Market Outlook card', 'marketOutlook-card.png', '16 / 10', 'Tool cards',
         'Card image for Market Outlook. 1600×1000.'),

    Slot('meal-planner', 'Meal Planner card', 'meal-planner-card.jpg', '16 / 10', 'Tool cards',
         'Card image for the Meal Planner. 1600×1000.'),

    Slot('about', 'About card', 'about-card.jpg', '16 / 10', 'Tool cards',
         'Card image for the About card. 1600×1000.'),

    Slot('bigger-projects', 'Bigger Projects card', 'bigger-projects-card.jpg', '16 / 10', 'Tool cards',
         'Card image for the Bigger Projects card. 1600×1000.'),

    Slot('philosophy-panel', 'Philosophy panel', 'philosophy-panel.jpg', '4 / 3', 'Home page',
         'Photograph beside "Builder by day". Renders 4:3 on desktop and 16:9 '
         'on mobile — keep the subject centred. A warm terracotta wash is '
         'applied on top automatically.'),

    Slot('portrait', 'About portrait', 'portrait.jpg', '1 / 1', 'About page',
         'Square headshot at the top of the About page. 800×800.'),
]

SLOTS = OrderedDict((s.id, s) for s in _SLOTS)

# filename -> Slot, for resolving an inbound /assets/<filename> request.
SLOTS_BY_FILENAME = {s.filename: s for s in _SLOTS}


def get(slot_id):
    return SLOTS.get(slot_id)


def by_filename(filename):
    return SLOTS_BY_FILENAME.get(filename)


def grouped():
    """Slots bucketed by their admin group, preserving registry order."""
    out = OrderedDict()
    for slot in SLOTS.values():
        out.setdefault(slot.group, []).append(slot)
    return out
