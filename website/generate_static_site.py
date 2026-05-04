from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from jsonschema import ValidationError, validate


APP_DIR = Path(__file__).resolve().parent
DIST_DIR = APP_DIR / 'dist'
STATIC_SOURCE_DIR = APP_DIR / 'static'
FLAT_STATIC_DIRS = ('css', 'data', 'fonts', 'images', 'js', 'video')

# Explicit route mapping keeps static export predictable and avoids accidental admin/debug routes.
ROUTE_OUTPUTS = {
    '/': 'index.html',
    '/film': 'film.html',
    '/media': 'media.html',
    '/connect': 'connect.html',
    '/patreon': 'patreon.html',
    '/watch': 'watch.html',
    '/credits': 'credits.html',
    '/map': 'map.html',
}

JSON_LD_ENVELOPE_SCHEMA = {
    'type': 'object',
    'required': ['@context'],
    'properties': {
        '@context': {
            'type': ['string', 'array', 'object'],
        },
        '@graph': {
            'type': 'array',
            'minItems': 1,
            'items': {
                'type': 'object',
                'required': ['@type'],
                'properties': {
                    '@type': {
                        'oneOf': [
                            {'type': 'string', 'minLength': 1},
                            {
                                'type': 'array',
                                'items': {'type': 'string', 'minLength': 1},
                                'minItems': 1,
                            },
                        ]
                    }
                },
                'additionalProperties': True,
            },
        },
        '@type': {
            'oneOf': [
                {'type': 'string', 'minLength': 1},
                {
                    'type': 'array',
                    'items': {'type': 'string', 'minLength': 1},
                    'minItems': 1,
                },
            ]
        },
    },
    'anyOf': [
        {'required': ['@graph']},
        {'required': ['@type']},
    ],
    'additionalProperties': True,
}


class StaticGenerationError(RuntimeError):
    pass


def route_href_to_output(href: str) -> str:
    if not href or not href.startswith('/'):
        return href

    if href.startswith('/static/'):
        return href.removeprefix('/static/')

    path, fragment = href.split('#', 1) if '#' in href else (href, '')

    if path in ROUTE_OUTPUTS:
        output = ROUTE_OUTPUTS[path]
        return f'{output}#{fragment}' if fragment else output

    if path == '/':
        return f'index.html#{fragment}' if fragment else 'index.html'

    return href


def rewrite_html_for_static_export(html_text: str) -> str:
    soup = BeautifulSoup(html_text, 'html.parser')
    public_static_prefix = 'https://www.openmicodyssey.com/static/'

    for tag in soup.find_all(True):
        for attribute in ('href', 'src', 'poster'):
            value = tag.get(attribute)
            if not value:
                continue

            if not isinstance(value, str):
                continue

            if value.startswith(public_static_prefix):
                tag[attribute] = value.removeprefix(public_static_prefix)
                continue

            if value.startswith('/static/') or value.startswith('/'):
                tag[attribute] = route_href_to_output(value)

    return str(soup)


def rewrite_css_for_static_export(css_text: str) -> str:
    css_text = css_text.replace('url("/static/images/', 'url("../images/')
    css_text = css_text.replace("url('/static/images/", "url('../images/")
    css_text = css_text.replace('url(/static/images/', 'url(../images/')
    css_text = css_text.replace('url("/static/video/', 'url("../video/')
    css_text = css_text.replace("url('/static/video/", "url('../video/")
    css_text = css_text.replace('url(/static/video/', 'url(../video/')
    return css_text


def normalize_doctype_case(html_text: str) -> str:
    return re.sub(r'<!doctype\s+html>', '<!doctype html>', html_text, flags=re.IGNORECASE)


def clean_html_whitespace(html_text: str) -> str:
    cleaned_lines = []
    previous_was_blank = False

    for line in html_text.splitlines():
        normalized_line = line.rstrip()
        if not normalized_line.strip():
            if previous_was_blank:
                continue
            previous_was_blank = True
            continue

        previous_was_blank = False
        cleaned_lines.append(normalized_line)

    cleaned_text = '\n'.join(cleaned_lines).strip()
    cleaned_text = re.sub(r'\n[\s\ufeff]*\n+', '\n', cleaned_text)
    cleaned_text = re.sub(r'(?i)<!doctype html>\s*<html',
                          '<!doctype html>\n<html', cleaned_text)
    return cleaned_text + '\n'


def build_flask_app():
    sys.path.insert(0, str(APP_DIR))
    from movie_site import create_app

    return create_app()


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def output_path_for(route: str) -> Path:
    relative_path = ROUTE_OUTPUTS[route]
    return DIST_DIR / relative_path


def build_redirect_html(location: str) -> str:
    static_location = route_href_to_output(location)
    escaped_location = static_location.replace('"', '&quot;')
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta http-equiv=\"refresh\" content=\"0;url={escaped_location}\" />
    <title>Redirecting...</title>
    <link rel=\"canonical\" href=\"{escaped_location}\" />
  </head>
  <body>
    <p>Redirecting to <a href=\"{escaped_location}\">{escaped_location}</a>.</p>
  </body>
</html>
"""


def validate_html_structure(html_text: str, route: str) -> BeautifulSoup:
    soup = BeautifulSoup(html_text, 'html.parser')
    if soup.html is None:
        raise StaticGenerationError(
            f'Missing <html> root element for route: {route}')
    if soup.head is None:
        raise StaticGenerationError(
            f'Missing <head> element for route: {route}')
    if soup.body is None:
        raise StaticGenerationError(
            f'Missing <body> element for route: {route}')
    return soup


def validate_json_ld(soup: BeautifulSoup, route: str) -> None:
    json_ld_scripts = soup.find_all(
        'script', attrs={'type': 'application/ld+json'})
    if not json_ld_scripts:
        raise StaticGenerationError(
            f'No JSON-LD script block found for route: {route}')

    for index, script in enumerate(json_ld_scripts, start=1):
        raw_json = script.string or script.get_text(strip=True)
        if not raw_json:
            raise StaticGenerationError(
                f'Empty JSON-LD block at route {route} (block #{index})'
            )

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise StaticGenerationError(
                f'Invalid JSON-LD JSON at route {route} (block #{index}): {exc}'
            ) from exc

        try:
            validate(instance=data, schema=JSON_LD_ENVELOPE_SCHEMA)
        except ValidationError as exc:
            raise StaticGenerationError(
                f'JSON-LD schema envelope validation failed at route {route} '
                f'(block #{index}): {exc.message}'
            ) from exc

        context_value = data.get('@context')
        if isinstance(context_value, str) and 'schema.org' not in context_value:
            raise StaticGenerationError(
                f'JSON-LD @context does not reference schema.org at route: {route}'
            )


def render_routes(app, dist_dir: Path) -> list[Path]:
    generated_files: list[Path] = []

    with app.test_client() as client:
        for route in ROUTE_OUTPUTS:
            response = client.get(route, follow_redirects=False)
            destination = output_path_for(route)

            if response.status_code in (301, 302, 307, 308):
                location = response.headers.get('Location')
                if not location:
                    raise StaticGenerationError(
                        f'Redirect route {route} missing Location header.'
                    )
                html = build_redirect_html(location)
            elif response.status_code == 200:
                html = response.get_data(as_text=True)
            else:
                raise StaticGenerationError(
                    f'Failed to render {route}: HTTP {response.status_code}'
                )

            soup = validate_html_structure(html, route)
            if response.status_code == 200:
                validate_json_ld(soup, route)
                html = rewrite_html_for_static_export(html)

            html = normalize_doctype_case(html)
            html = clean_html_whitespace(html)

            write_text_file(destination, html)
            generated_files.append(destination)

    return generated_files


def render_metadata_files(app, dist_dir: Path) -> list[Path]:
    generated_files: list[Path] = []
    metadata_routes = {
        '/robots.txt': 'robots.txt',
        '/sitemap.xml': 'sitemap.xml',
    }

    with app.test_client() as client:
        for route, output_name in metadata_routes.items():
            response = client.get(route, follow_redirects=False)
            if response.status_code != 200:
                raise StaticGenerationError(
                    f'Failed to render {route}: HTTP {response.status_code}'
                )

            output_path = dist_dir / output_name
            write_text_file(output_path, response.get_data(as_text=True))
            generated_files.append(output_path)

    return generated_files


def copy_static_assets() -> None:
    if not STATIC_SOURCE_DIR.exists():
        raise StaticGenerationError(
            f'Static source directory not found: {STATIC_SOURCE_DIR}')

    for directory_name in FLAT_STATIC_DIRS:
        source_path = STATIC_SOURCE_DIR / directory_name
        destination_path = DIST_DIR / directory_name

        if not source_path.exists():
            continue

        if destination_path.exists():
            shutil.rmtree(destination_path)

        shutil.copytree(source_path, destination_path)

        if directory_name == 'css':
            for css_file in destination_path.rglob('*.css'):
                css_file.write_text(
                    rewrite_css_for_static_export(
                        css_file.read_text(encoding='utf-8')
                    ),
                    encoding='utf-8',
                )


def generate_static_site(clean: bool = True) -> list[Path]:
    if clean and DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    app = build_flask_app()
    generated_files = render_routes(app, DIST_DIR)
    generated_files.extend(render_metadata_files(app, DIST_DIR))
    copy_static_assets()
    return generated_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Render Flask routes as a deployable static site bundle in website/dist/.'
    )
    parser.add_argument(
        '--no-clean',
        action='store_true',
        help='Do not remove website/dist/ before generating files.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_files = generate_static_site(
        clean=not args.no_clean,
    )

    print(f'Generated {len(generated_files)} HTML files in {DIST_DIR}')
    for file_path in generated_files:
        print(f' - {file_path.relative_to(APP_DIR)}')
    for directory_name in FLAT_STATIC_DIRS:
        destination_path = DIST_DIR / directory_name
        if destination_path.exists():
            print(f' - {destination_path.relative_to(APP_DIR)} (static assets)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
