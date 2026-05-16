from . import render_schema_template
from ..db import get_dict_cursor


def build_organization_node(organization_id, organization_name):
    cursor = get_dict_cursor()
    cursor.execute(
        "SELECT * FROM organization WHERE name = %s",
        (organization_name,),
    )
    organization = cursor.fetchone()

    cursor.close()

    if not organization:
        return None

    return render_schema_template(
        'organization.json',
        organization_id=organization_id,
        organization=organization,
    )
