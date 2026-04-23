from . import render_schema_template


def build_organization_node(movie, organization_id):
    return render_schema_template(
        'organization.json',
        organization_id=organization_id,
        organization=movie['production_company'],
    )
