from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from jsonschema import ValidationError, validate


ROOT_DIR = Path(__file__).resolve().parent
WEBSITE_DIR = ROOT_DIR / 'website'
DIST_DIR = ROOT_DIR / 'dist'
STATIC_SOURCE_DIR = WEBSITE_DIR / 'static'
STATIC_DEST_DIR = DIST_DIR / 'static'

# Explicit route mapping keeps static export predictable and avoids accidental admin/debug routes.
ROUTE_OUTPUTS = {
    '/': 'index.html',
    '/film': 'film.html',
    '/media': 'media.html',
    '/connect': 'connect.html',
    '/patreon': 'patreon.html',
    '/watch': 'watch.html',
    '/credits': 'credits.html',
}

JSON_LD_ENVELOPE_SCHEMA = {
    'type': 'object',
    'required': ['@context', '@graph'],
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
    },
    'additionalProperties': True,
}


class StaticGenerationError(RuntimeError):
    pass


def build_flask_app():
    sys.path.insert(0, str(WEBSITE_DIR))
    from movie_site import create_app

    return create_app()


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def output_path_for(route: str) -> Path:
    relative_path = ROUTE_OUTPUTS[route]
    return DIST_DIR / relative_path


def build_redirect_html(location: str) -> str:
    escaped_location = location.replace('"', '&quot;')
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

            write_text_file(destination, html)
            generated_files.append(destination)

    return generated_files


def copy_static_assets() -> None:
    if not STATIC_SOURCE_DIR.exists():
        raise StaticGenerationError(
            f'Static source directory not found: {STATIC_SOURCE_DIR}')

    if STATIC_DEST_DIR.exists():
        shutil.rmtree(STATIC_DEST_DIR)

    shutil.copytree(STATIC_SOURCE_DIR, STATIC_DEST_DIR)


def generate_static_site(clean: bool = True) -> list[Path]:
    if clean and DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    app = build_flask_app()
    generated_files = render_routes(app, DIST_DIR)
    copy_static_assets()
    return generated_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Render Flask routes as a deployable static site bundle in dist/.'
    )
    parser.add_argument(
        '--no-clean',
        action='store_true',
        help='Do not remove dist/ before generating files.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_files = generate_static_site(clean=not args.no_clean)

    print(f'Generated {len(generated_files)} HTML files in {DIST_DIR}')
    for file_path in generated_files:
        print(f' - {file_path.relative_to(ROOT_DIR)}')
    print(f' - {STATIC_DEST_DIR.relative_to(ROOT_DIR)} (static assets)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
