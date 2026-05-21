import json

from flask import current_app

from .schema_parts.graph import build_movie_schema_graph
from .schema_parts.social import build_org_social_schema_json as build_org_social_schema_json_for_site


def build_movie_schema_json(movie):
    return json.dumps(build_movie_schema_graph(movie), indent=2, sort_keys=False)


def build_org_social_schema_json(movie):
    site_url = current_app.config['SITE_URL'].rstrip('/')
    return build_org_social_schema_json_for_site(movie, site_url)
