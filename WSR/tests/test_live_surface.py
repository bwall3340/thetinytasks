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
        body = body[:body.index('function flattenArea(')]
        assert 'for (let y = 0' in body and 'for (let x = 0' in body
        assert 'stack' not in body, 'magic wand should not be a flood fill'
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
