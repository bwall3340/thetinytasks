"""
Live-surface contract tests.

These lock down what the deployed site actually depends on, so that removing
unused or duplicated code cannot silently break a live journey.

They are derived from the shipped files rather than from hard-coded lists: if a
page starts calling a new endpoint, or a tool card is added, the tests follow.
That is the point — a hard-coded list would still pass after someone deletes
the route out from under it.

Run with:
    cd WSR
    pytest tests/test_live_surface.py -v
"""

import io
import os
import re

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound

from conftest import make_png_with_white_bg

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WSR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


# ---------------------------------------------------------------------------
# Helpers — discover the live surface from the files themselves
# ---------------------------------------------------------------------------

def read(path):
    with io.open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


FETCH_RE = re.compile(r"""fetch\(\s*(['"`])(.*?)\1""", re.DOTALL)
CONST_URL_RE = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*['"](https?://[^'"]+)['"]""")


def same_origin_fetch_targets(source):
    """
    Every path a file fetches from its own origin, with the request method.

    A `${VAR}` prefix is treated as same-origin unless the file assigns VAR to
    an absolute http(s) literal — that is how data-finder.html's external
    DataFinderAgent service is correctly excluded while background-remover's
    `${API_BASE}` (window.location.origin) is correctly included.
    """
    external_vars = {name for name, _ in CONST_URL_RE.findall(source)}
    targets = []

    for match in FETCH_RE.finditer(source):
        literal = match.group(2)

        prefix = re.match(r'\$\{(\w+)\}', literal)
        if prefix:
            if prefix.group(1) in external_vars:
                continue                      # a different service, not ours
            literal = literal[prefix.end():]
        elif literal.startswith(('http://', 'https://', '//')):
            continue

        if not literal.startswith('/'):
            continue

        # Look just past the call for an explicit method.
        tail = source[match.end():match.end() + 400]
        method_match = re.search(r"""method\s*:\s*['"](\w+)['"]""", tail)
        method = (method_match.group(1) if method_match else 'GET').upper()

        # `/market/admin/sources/${id}/scrape` -> `/market/admin/sources/1/scrape`
        # so the path can be matched against Flask's converters.
        literal = re.sub(r'\$\{[^}]*\}', '1', literal)

        targets.append((literal, method))

    return targets


def rendered_templates():
    """Template names any Python module actually renders."""
    names = set()
    for dirpath, dirnames, filenames in os.walk(WSR_DIR):
        dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'tests', 'site')]
        for filename in filenames:
            if filename.endswith('.py'):
                source = read(os.path.join(dirpath, filename))
                names.update(re.findall(r"""render_template\(\s*['"]([^'"]+)['"]""", source))
    return names


def static_files_referenced_by(template_source):
    """Static filenames a template pulls in."""
    return set(
        re.findall(r"""url_for\(\s*['"]static['"]\s*,\s*filename\s*=\s*['"]([^'"]+)['"]""",
                   template_source)
    ) | set(re.findall(r"""["']/static/([^"'?]+)""", template_source))


def live_source_files():
    """
    Every HTML/JS file a visitor can actually reach, as (label, source) pairs.

    Two halves: static site files that have a Flask route, and templates that a
    route renders plus the static assets those templates reference.
    """
    from app import app, SITE_DIR

    adapter = app.url_map.bind('localhost')
    files = []

    def route_exists(path):
        try:
            adapter.match(path, method='GET')
        except NotFound:
            return False
        except MethodNotAllowed:
            return True
        return True

    # Static site files, reachable through their own routes.
    for dirpath, dirnames, filenames in os.walk(SITE_DIR):
        dirnames[:] = [d for d in dirnames
                       if d not in ('.git', 'WSR', 'DataFinderAgent', 'node_modules',
                                    'assets', 'sanity', '__pycache__')]
        for filename in sorted(filenames):
            if not filename.endswith(('.html', '.js')):
                continue
            full = os.path.join(dirpath, filename)
            url = '/' + os.path.relpath(full, SITE_DIR).replace(os.sep, '/')
            if filename == 'index.html' and not route_exists(url):
                # Served at the directory path (the home page is '/').
                url = url[:-len('index.html')]
            if route_exists(url):
                files.append((url, read(full)))

    # Templates a route renders, plus the static files they reference.
    for name in sorted(rendered_templates()):
        template_path = os.path.join(WSR_DIR, 'templates', name)
        if not os.path.exists(template_path):
            continue
        source = read(template_path)
        files.append(('templates/' + name, source))
        for static_name in sorted(static_files_referenced_by(source)):
            static_path = os.path.join(WSR_DIR, 'static', static_name)
            if static_path.endswith('.js') and os.path.exists(static_path):
                files.append(('static/' + static_name, read(static_path)))

    return files


# ---------------------------------------------------------------------------
# No dead API calls — CLAUDE.md journey rule, enforced
# ---------------------------------------------------------------------------

class TestNoDeadApiCalls:
    """Every same-origin fetch on a reachable page must hit a real route."""

    def test_live_surface_is_not_empty(self):
        # Guards the discovery helpers themselves: a bug that returned nothing
        # would make every other test in this class vacuously pass.
        labels = [label for label, _ in live_source_files()]
        assert '/background-remover.html' in labels
        assert '/' in labels, 'the home page itself should be part of the live surface'

    def test_every_fetch_target_resolves(self, app):
        adapter = app.url_map.bind('localhost')
        dead = []

        for label, source in live_source_files():
            for path, method in same_origin_fetch_targets(source):
                try:
                    adapter.match(path, method=method)
                except NotFound:
                    dead.append(f'{label} -> {method} {path} (no such route)')
                except MethodNotAllowed:
                    dead.append(f'{label} -> {method} {path} (route exists, wrong method)')

        assert not dead, 'Dead API calls on the live surface:\n  ' + '\n  '.join(dead)

    def test_background_remover_calls_are_all_live(self, app):
        """The live tool's own contract, called out explicitly."""
        adapter = app.url_map.bind('localhost')
        source = read(os.path.join(REPO_ROOT, 'background-remover.html'))
        targets = same_origin_fetch_targets(source)

        assert targets, 'background-remover.html should call the Flask backend'

        for path, method in targets:
            adapter.match(path, method=method)  # raises if the route is gone

    @pytest.mark.parametrize('endpoint', [
        '/process_interactive',
        '/process_vtracer',
        '/process_upscale',
    ])
    def test_endpoints_the_live_tool_needs_still_exist(self, app, endpoint):
        """Named so a deletion that removes one of these fails loudly."""
        app.url_map.bind('localhost').match(endpoint, method='POST')


# ---------------------------------------------------------------------------
# Every page the live site links to must be served
# ---------------------------------------------------------------------------

LIVE_PAGES = [
    '/',
    '/background-remover.html',
    '/return-stream.html',
    '/data-finder.html',
    '/about.html',
    '/bigger-projects.html',
    '/styles.css',
    '/script.js',
    '/shared.css',
]


class TestLivePageRoutes:
    @pytest.mark.parametrize('path', LIVE_PAGES)
    def test_page_is_served(self, client, path):
        response = client.get(path)
        assert response.status_code == 200, f'{path} is linked from the site but not served'
        assert response.data, f'{path} served an empty body'

    def test_sankey_tool_is_served(self, client):
        response = client.get('/Sankey/sankey_chart_tool (15).html')
        assert response.status_code == 200

    def test_assets_route_serves_a_committed_image(self, client):
        response = client.get('/assets/hero.jpg')
        assert response.status_code == 200
        assert len(response.data) > 0


# ---------------------------------------------------------------------------
# Home page tool cards must route somewhere real
# ---------------------------------------------------------------------------

class TestHomePageToolRouting:
    """CLAUDE.md: no orphaned tool cards."""

    def _launch_tool_cases(self):
        source = read(os.path.join(REPO_ROOT, 'script.js'))
        body = source[source.index('launchTool(toolName)'):]
        body = body[:body.index('showComingSoonModal(toolName)')]
        return set(re.findall(r"""case\s+['"]([^'"]+)['"]""", body)), body

    def test_every_card_has_a_launch_case_or_falls_through(self):
        index = read(os.path.join(REPO_ROOT, 'index.html'))
        cards = set(re.findall(r'''data-tool=["']([^"']+)["']''', index))
        cases, _ = self._launch_tool_cases()

        # 'coming-soon' intentionally falls through to the modal.
        unhandled = cards - cases - {'coming-soon'}
        assert not unhandled, f'Tool cards with no launchTool case: {sorted(unhandled)}'

    def test_every_launch_target_exists(self, client):
        _, body = self._launch_tool_cases()
        targets = re.findall(r"""window\.location\.href\s*=\s*['"]([^'"]+)['"]""", body)
        assert targets, 'launchTool should route somewhere'

        missing = []
        for target in targets:
            if target.startswith('./'):
                if not os.path.exists(os.path.join(REPO_ROOT, target[2:])):
                    missing.append(f'{target} (file not in repo)')
            elif target.startswith('/'):
                response = client.get(target, follow_redirects=True)
                if response.status_code != 200:
                    missing.append(f'{target} (serves {response.status_code})')

        assert not missing, 'launchTool routes to nothing:\n  ' + '\n  '.join(missing)


# ---------------------------------------------------------------------------
# Docker image must contain exactly what the routes serve
# ---------------------------------------------------------------------------

class TestDockerSiteFiles:
    """
    A deletion that removes a file but leaves its COPY line breaks the build;
    one that removes a COPY but leaves the route breaks the page in production
    only. Both are caught here.
    """

    def _copy_lines(self):
        dockerfile = read(os.path.join(REPO_ROOT, 'Dockerfile'))
        return re.findall(r'^COPY\s+(\S+)\s+(\S+)\s*$', dockerfile, re.MULTILINE)

    def test_every_copied_path_exists(self):
        missing = [
            src for src, dest in self._copy_lines()
            if dest.startswith('/app/site') and not os.path.exists(
                os.path.join(REPO_ROOT, src.rstrip('/')))
        ]
        assert not missing, f'Dockerfile copies paths that do not exist: {missing}'

    def test_every_site_route_target_is_copied(self):
        copied = {os.path.basename(src.rstrip('/')) for src, _ in self._copy_lines()}
        app_source = read(os.path.join(WSR_DIR, 'app.py'))
        served = set(re.findall(
            r"""send_from_directory\(\s*SITE_DIR\s*,\s*['"]([^'"]+)['"]""", app_source))

        not_copied = sorted(served - copied)
        assert not not_copied, (
            'Routes serve files the Docker image never copies '
            f'(they would 404 in production): {not_copied}')


# ---------------------------------------------------------------------------
# /process_vtracer — the live tool's vectorizer, previously untested
# ---------------------------------------------------------------------------

class TestProcessVtracer:
    ENDPOINT = '/process_vtracer'

    def _post(self, client, image_bytes=None, **params):
        data = {}
        if image_bytes is not None:
            data['image'] = (io.BytesIO(image_bytes), 'logo.png')
        data.update(params)
        return client.post(self.ENDPOINT, data=data, content_type='multipart/form-data')

    def test_no_image_returns_error(self, client):
        response = self._post(client)
        assert response.status_code == 200
        assert json.loads(response.data)['success'] is False

    def test_empty_filename_returns_error(self, client):
        response = client.post(
            self.ENDPOINT,
            data={'image': (io.BytesIO(b''), '')},
            content_type='multipart/form-data')
        assert json.loads(response.data)['success'] is False

    def test_valid_image_returns_svg(self, client):
        response = self._post(client, make_png_with_white_bg())
        payload = json.loads(response.data)
        assert payload['success'] is True, payload.get('error')
        assert payload['svg_content'].lstrip().startswith(('<svg', '<?xml'))

    def test_svg_is_well_formed_xml(self, client):
        import xml.etree.ElementTree as ET
        payload = json.loads(self._post(client, make_png_with_white_bg()).data)
        ET.fromstring(payload['svg_content'])  # raises on malformed output

    @pytest.mark.parametrize('field,value', [
        ('filter_speckle', '4'),
        ('color_precision', '6'),
        ('layer_difference', '16'),
        ('corner_threshold', '60'),
    ])
    def test_tuning_parameters_are_accepted(self, client, field, value):
        """The live page exposes all four as sliders."""
        payload = json.loads(
            self._post(client, make_png_with_white_bg(), **{field: value}).data)
        assert payload['success'] is True, payload.get('error')

    def test_cors_header_present(self, client):
        response = self._post(client, make_png_with_white_bg())
        assert response.headers.get('Access-Control-Allow-Origin') == '*'


import json  # noqa: E402  (used by the vtracer tests above)


# ---------------------------------------------------------------------------
# Upscale options the live page exposes must reach the backend
# ---------------------------------------------------------------------------

class TestUpscaleOptionsAreHonoured:
    """
    Every checkbox on the upscaler must change the output. A control that is
    sent but ignored is a silent failure, which CLAUDE.md forbids.
    """

    ENDPOINT = '/process_upscale'

    def _upscale(self, client, **params):
        data = {'image': (io.BytesIO(make_png_with_white_bg()), 'logo.png'),
                'scale_factor': '2'}
        data.update(params)
        response = client.post(self.ENDPOINT, data=data,
                               content_type='multipart/form-data')
        payload = json.loads(response.data)
        assert payload['success'] is True, payload.get('error')
        return payload['upscaled_image']

    def test_page_sends_every_option_the_route_reads(self):
        """The form fields the live page posts must all be read server-side."""
        page = read(os.path.join(REPO_ROOT, 'background-remover.html'))
        upscale_block = page[page.index('/process_upscale') - 3000:
                             page.index('/process_upscale')]
        sent = set(re.findall(r"""formData\.append\(\s*['"](\w+)['"]""", upscale_block))

        route = read(os.path.join(WSR_DIR, 'app.py'))
        route_block = route[route.index("@app.route('/process_upscale'"):]
        route_block = route_block[:route_block.index('@app.errorhandler')]
        read_fields = set(re.findall(r"""request\.form\.get\(\s*['"](\w+)['"]""", route_block))

        ignored = sent - read_fields - {'image'}
        assert not ignored, (
            'background-remover.html posts fields /process_upscale never reads, '
            f'so the control does nothing: {sorted(ignored)}')

    def test_enhance_edges_changes_the_output(self, client):
        on = self._upscale(client, enhance_edges='true')
        off = self._upscale(client, enhance_edges='false')
        assert on != off, 'the Enhance Edges checkbox had no effect'

    def test_enhance_edges_defaults_to_on(self, client):
        assert self._upscale(client) == self._upscale(client, enhance_edges='true')

    def test_flatten_background_changes_the_output(self, client):
        off = self._upscale(client, flatten_background='false')
        on = self._upscale(client, flatten_background='true', tolerance='40')
        assert on != off, 'the Flatten Background checkbox had no effect'

    def test_flatten_background_defaults_to_off(self, client):
        assert self._upscale(client) == self._upscale(client, flatten_background='false')

    def test_out_of_range_tolerance_is_rejected(self, client):
        response = client.post(
            self.ENDPOINT,
            data={'image': (io.BytesIO(make_png_with_white_bg()), 'logo.png'),
                  'flatten_background': 'true', 'tolerance': '900'},
            content_type='multipart/form-data')
        payload = json.loads(response.data)
        assert payload['success'] is False
        assert 'tolerance' in payload['error'].lower()


# ---------------------------------------------------------------------------
# Every tool in the editor's dropdown must actually do something
# ---------------------------------------------------------------------------

class TestEditorToolModes:
    """
    Magic Wand shipped in the dropdown for months with no branch in
    handleCanvasClick, so selecting it silently did nothing.
    """

    def _page(self):
        return read(os.path.join(REPO_ROOT, 'background-remover.html'))

    def test_every_tool_mode_option_is_handled(self):
        page = self._page()

        select = page[page.index('<select id="toolMode">'):]
        select = select[:select.index('</select>')]
        options = set(re.findall(r'<option value="([^"]+)"', select))

        handler = page[page.index('function handleCanvasClick'):]
        handler = handler[:handler.index('function handleMouseDown')]
        handled = set(re.findall(r"""toolMode === ['"](\w+)['"]""", handler))

        # 'brush' is handled by the mousedown/mousemove path, not by click.
        brush_path = page[page.index('function handleMouseDown'):
                          page.index('function handleBrushAction')]
        handled |= set(re.findall(r"""value !== ['"](\w+)['"]""", brush_path))

        unhandled = options - handled
        assert not unhandled, (
            f'Tool modes offered in the UI that no code responds to: {sorted(unhandled)}')

    def test_magic_wand_is_implemented(self):
        page = self._page()
        assert 'function magicWandRemove(' in page
        assert "toolMode === 'magic'" in page

    def test_magic_wand_is_non_contiguous(self):
        """Its whole point: it must scan the image, not flood-fill from a seed."""
        page = self._page()
        body = page[page.index('function magicWandRemove('):]
        body = body[:body.index('\n        function ', 10)]

        assert 'data.length' in body, 'magic wand must scan the whole buffer'
        assert 'stack' not in body, 'magic wand should not be a flood fill'
        assert 'collectRegion(' not in body, 'that walk is contiguous by design'
        assert 'saveToHistory()' in body, 'magic wand must be undoable'


# ---------------------------------------------------------------------------
# Nothing server-side may become unreachable again
# ---------------------------------------------------------------------------

class TestNoOrphanedServerFiles:
    """
    Three generations of the same tool accumulated here because a template
    could stop being rendered without anything noticing. This fails the moment
    a template or static file stops being reachable, so the next superseded UI
    gets deleted with the change that supersedes it.
    """

    def test_every_template_is_rendered(self):
        rendered = rendered_templates()
        templates_dir = os.path.join(WSR_DIR, 'templates')

        orphans = []
        for dirpath, _, filenames in os.walk(templates_dir):
            for filename in filenames:
                if not filename.endswith('.html'):
                    continue
                name = os.path.relpath(
                    os.path.join(dirpath, filename), templates_dir).replace(os.sep, '/')
                if name not in rendered:
                    orphans.append(name)

        assert not orphans, (
            'Templates no route renders — delete them or wire them up: '
            f'{sorted(orphans)}')

    def test_every_static_file_is_referenced(self):
        static_dir = os.path.join(WSR_DIR, 'static')
        if not os.path.isdir(static_dir):
            pytest.skip('no static directory')

        referenced = set()
        for name in rendered_templates():
            path = os.path.join(WSR_DIR, 'templates', name)
            if os.path.exists(path):
                referenced |= static_files_referenced_by(read(path))

        orphans = [f for f in sorted(os.listdir(static_dir))
                   if not f.startswith('.') and f not in referenced]

        assert not orphans, (
            f'Static files no rendered template references: {orphans}')

    def test_every_python_module_is_imported(self):
        """Catches the next lambda_function.py before it sits for six months."""
        imported = set()
        for dirpath, dirnames, filenames in os.walk(WSR_DIR):
            dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'site')]
            for filename in filenames:
                if filename.endswith('.py'):
                    source = read(os.path.join(dirpath, filename))
                    imported |= set(re.findall(r'^\s*(?:from|import)\s+(\w+)',
                                               source, re.MULTILINE))

        modules = [f[:-3] for f in os.listdir(WSR_DIR)
                   if f.endswith('.py') and f != 'app.py']

        orphans = sorted(m for m in modules if m not in imported)
        assert not orphans, f'Python modules nothing imports: {orphans}'


# ---------------------------------------------------------------------------
# Links between pages must not rot
# ---------------------------------------------------------------------------

class TestInternalLinks:
    """
    The Sankey tool linked to ../WhiteBackgroundRemover/index.html long after
    the site had moved on. Relative links between tool pages get no coverage
    from route tests, so check them directly.
    """

    def test_every_relative_link_resolves(self):
        from app import SITE_DIR

        broken = []
        for dirpath, dirnames, filenames in os.walk(SITE_DIR):
            dirnames[:] = [d for d in dirnames
                           if d not in ('.git', 'WSR', 'DataFinderAgent',
                                        'node_modules', 'sanity', '__pycache__')]
            for filename in filenames:
                if not filename.endswith('.html'):
                    continue
                page = os.path.join(dirpath, filename)
                source = read(page)

                for href in re.findall(r'''<a\s[^>]*href=["']([^"'#]+)["']''', source):
                    if href.startswith(('http://', 'https://', 'mailto:', '/', '#', 'javascript:')):
                        continue
                    if '${' in href:
                        continue  # built at runtime by a JS template literal
                    target = os.path.normpath(os.path.join(dirpath, href.split('?')[0]))
                    if not os.path.exists(target):
                        rel = os.path.relpath(page, SITE_DIR)
                        broken.append(f'{rel} -> {href}')

        assert not broken, 'Relative links pointing at nothing:\n  ' + '\n  '.join(broken)


# ---------------------------------------------------------------------------
# Editor foundation — the document must survive import
# ---------------------------------------------------------------------------

class TestDocumentModel:
    """
    Every upload used to be downscaled to 800x600 before editing, and that
    downscaled canvas was what went to the backend — so a 2x upscale of a
    2400px logo returned something smaller than the file the user supplied.
    """

    def _page(self):
        return read(os.path.join(REPO_ROOT, 'background-remover.html'))

    def test_uploads_are_not_downscaled_for_display(self):
        page = self._page()
        loader = page[page.index('function loadImageToCanvas'):]
        loader = loader[:loader.index('function setupCanvasInteraction')]

        assert 'maxWidth = 800' not in loader, 'the 800x600 import cap is back'
        assert 'maxHeight = 600' not in loader
        assert 'MAX_DOCUMENT_PIXELS' in loader, (
            'the document should only be bounded by a memory ceiling')

    def test_canvas_scales_proportionally(self):
        """max-width alone squashes a canvas; height:auto keeps the ratio."""
        page = self._page()
        rule = page[page.index('#imageCanvas {'):]
        rule = rule[:rule.index('}')]
        assert 'max-width: 100%' in rule
        assert 'height: auto' in rule, 'a native-resolution canvas would be squashed'

    def test_click_mapping_uses_bounding_rect(self):
        """Display is CSS-scaled, so coordinates must come from the rect."""
        page = self._page()
        handler = page[page.index('function handleCanvasClick'):]
        handler = handler[:handler.index('function handleMouseDown')]
        assert 'getBoundingClientRect()' in handler
        assert 'offsetX' not in handler and 'offsetY' not in handler


class TestEditPerformance:
    """
    The import cap existed to hide a slow flood fill: a Set of "x,y" strings
    plus an object per pixel cost ~7s on a 2400x2400 document. Removing the cap
    is only safe while the typed-array implementation is in place.
    """

    def _page(self):
        return read(os.path.join(REPO_ROOT, 'background-remover.html'))

    def test_region_fill_uses_typed_arrays(self):
        page = self._page()
        body = page[page.index('function collectRegion('):]
        body = body[:body.index('function removeBackground(')]

        assert 'Uint8Array' in body, 'visited mask should be a typed array'
        assert 'Int32Array' in body, 'the stack should be a flat integer array'
        assert 'new Set' not in body, 'a Set of coordinate strings is the slow path'
        assert 'push({' not in body, 'no per-pixel object allocation'

    @pytest.mark.parametrize('fn', ['removeBackground', 'flattenArea'])
    def test_fills_share_one_region_walk(self, fn):
        page = self._page()
        body = page[page.index(f'function {fn}('):]
        body = body[:body.index('\n        function ', 10)]
        assert 'collectRegion(' in body, f'{fn} should reuse the shared region walk'
        assert 'new Set' not in body

    def test_magic_wand_has_no_per_pixel_allocation(self):
        page = self._page()
        body = page[page.index('function magicWandRemove('):]
        body = body[:body.index('\n        function ', 10)]
        assert 'getPixelColor' not in body, (
            'allocating an object per pixel across a full-image scan is the slow path')


class TestHistoryIsBounded:
    """A full snapshot per step is ~23MB on a 2400x2400 document."""

    def test_history_is_capped(self):
        page = read(os.path.join(REPO_ROOT, 'background-remover.html'))
        body = page[page.index('function saveToHistory()'):]
        body = body[:body.index('\n        document.getElementById(\'undoBtn\').addEventListener')]

        assert 'HISTORY_BYTE_BUDGET' in body, 'history must be bounded by memory'
        assert 'HISTORY_MAX_STEPS' in body, 'history must be bounded by step count'
        assert 'splice(1, 1)' in body, 'the original must be preserved for Reset'


class TestTransportFitting:
    """
    canvas.toBlob re-encodes far larger than the source file, so a
    native-resolution document has to be fitted for the request even though it
    is kept intact locally.
    """

    def _page(self):
        return read(os.path.join(REPO_ROOT, 'background-remover.html'))

    def test_frontend_limit_matches_the_route_limit(self):
        """
        The page must not guess the backend's ceiling. If someone raises the
        route limit, this fails until the page is updated to match.
        """
        page = self._page()
        match = re.search(r'const TRANSPORT_BYTE_LIMIT\s*=\s*([\d\s*]+);', page)
        assert match, 'the page should declare its transport limit'
        frontend = eval(match.group(1))            # a literal arithmetic expression

        route = read(os.path.join(WSR_DIR, 'app.py'))
        limits = set(re.findall(r'len\(image_data\)\s*>\s*([\d\s*]+):', route))
        assert limits, 'the routes should enforce a size limit'
        backend = {eval(limit) for limit in limits}

        assert backend == {frontend}, (
            f'the page fits uploads to {frontend} bytes but the routes reject '
            f'above {backend} — they must agree')

    def test_no_raw_toblob_reaches_the_backend(self):
        page = self._page()
        for endpoint in ('/process_interactive', '/process_vtracer', '/process_upscale'):
            block = page[:page.index(endpoint)]
            block = block[block.rindex('async function'):]
            assert 'encodeForTransport()' in block, (
                f'the {endpoint} call should fit the payload first')
            assert 'canvas.toBlob' not in block, (
                f'the {endpoint} call sends the raw canvas, which a large '
                'document will blow past the size limit')

    def test_fitting_is_never_silent(self):
        """CLAUDE.md: no silent failures."""
        page = self._page()
        assert page.count("noticeIfFitted(fitted, '") == 3, (
            'every backend call that may run on a fitted copy must say so')

        notice = page[page.index('function noticeIfFitted'):]
        notice = notice[:notice.index('\n        //')]
        assert 'showDocumentNotice(' in notice
        assert 'unchanged' in notice, 'the user should be told their document is intact'


# ---------------------------------------------------------------------------
# Design system — tokens must actually resolve
# ---------------------------------------------------------------------------

PALETTE = {
    '#F7F3EC', '#66725B', '#4D5645', '#B46B4E', '#D9CCBD', '#2B2A28', '#E7DED2',
    '#A8814A', '#8C4A34',
}

# Transparency checkerboard — a UI convention, not brand colour.
COLOUR_ALLOWLIST = {'#f0f0f0'}


class TestDesignTokens:
    """
    background-remover.html linked styles.css but not shared.css, where the
    tokens are defined. Every var() on the page resolved to nothing, so the
    fixed header had no background and page content scrolled through it.
    """

    def _pages(self):
        from app import SITE_DIR
        for name in sorted(os.listdir(SITE_DIR)):
            if name.endswith('.html'):
                yield name, read(os.path.join(SITE_DIR, name))

    @staticmethod
    def _links(source, filename):
        """A real <link> element, not a mention in a comment."""
        return re.search(
            r'<link[^>]+href=["\']/?' + re.escape(filename) + r'["\']', source) is not None

    def _tokens_defined_in(self, source):
        """Tokens a file declares itself, e.g. an inline :root block."""
        return set(re.findall(r'(--[\w-]+)\s*:', source))

    def _tokens_used_in(self, source):
        return set(re.findall(r'var\((--[\w-]+)', source))

    def test_every_page_can_resolve_the_tokens_it_uses(self):
        """
        A page resolves tokens from its own :root or from shared.css. Using one
        with neither in reach is silent: the declaration is simply dropped, so
        a fixed header loses its background and nothing errors.
        """
        from app import SITE_DIR
        shared = self._tokens_defined_in(read(os.path.join(SITE_DIR, 'shared.css')))
        styles_source = read(os.path.join(SITE_DIR, 'styles.css'))

        broken = []
        for name, source in self._pages():
            used = self._tokens_used_in(source)
            if self._links(source, 'styles.css'):
                used |= self._tokens_used_in(styles_source)
            if not used:
                continue

            available = self._tokens_defined_in(source)
            if self._links(source, 'shared.css'):
                available |= shared

            missing = sorted(used - available)
            if missing:
                broken.append(f'{name} cannot resolve {missing}')

        assert not broken, ('Pages using tokens they cannot resolve:\n  '
                            + '\n  '.join(broken))

    def test_tool_page_uses_no_off_palette_colours(self):
        """design.md: no neon. The tools had drifted to emerald/amber/red."""
        from app import SITE_DIR
        source = read(os.path.join(SITE_DIR, 'background-remover.html'))

        found = {c for c in re.findall(r'#[0-9a-fA-F]{6}', source)}
        off = sorted(c for c in found
                     if c.upper() not in PALETTE and c.lower() not in COLOUR_ALLOWLIST)

        assert not off, (
            f'Off-palette colours on the tool page: {off}. Use a token from '
            'shared.css, or add it to the palette in design.md first.')


class TestDocumentNoticePlacement:
    def test_notice_does_not_sit_over_the_action_buttons(self):
        """It was bottom-centre, directly on top of Vectorize."""
        page = read(os.path.join(REPO_ROOT, 'background-remover.html'))
        block = page[page.index('function showDocumentNotice'):]
        block = block[:block.index('// Encode the document')]

        assert 'right:' in block, 'the notice should be offset from the action column'
        assert 'left: 50%' not in block, 'bottom-centre covers the primary action'
