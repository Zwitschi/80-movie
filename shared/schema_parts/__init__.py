"""Schema.org JSON-LD generation helpers."""

import json
import re


def render_schema_template(template_name, **context):
    """Render a schema template from the schema/ directory.

    For Flask usage, this uses Flask's render_template.
    For standalone usage, templates are loaded from the shared package.
    """
    # Try Flask render_template first
    try:
        from flask import render_template as flask_render_template
        rendered = flask_render_template(f'schema/{template_name}', **context)
        return json.loads(rendered)
    except (ImportError, RuntimeError):
        # Standalone mode - load template directly
        from pathlib import Path
        template_path = Path(__file__).parent.parent / \
            'website' / 'templates' / 'schema' / template_name
        if template_path.exists():
            template_content = template_path.read_text()
            # Simple template variable substitution
            rendered = template_content
            for key, value in context.items():
                rendered = rendered.replace(f'{{{{ {key} }}}}', str(value))
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
            return json.loads(rendered)
        raise FileNotFoundError(f"Schema template not found: {template_name}")


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
