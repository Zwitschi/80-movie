import json
import re

from flask import current_app, render_template


def render_schema_template(template_name, **context):
    rendered = render_template(f'schema/{template_name}', **context)
    return json.loads(rendered)


def slugify_name(name):
    normalized = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return normalized or 'person'


def generate_unique_person_id(base_url, person_name, slug_counts):
    slug = slugify_name(person_name)
    current_count = slug_counts.get(slug, 0) + 1
    slug_counts[slug] = current_count

    if current_count == 1:
        return f'{base_url}/#person-{slug}'

    return f'{base_url}/#person-{slug}-{current_count}'
