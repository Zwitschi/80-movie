"""Shared movie data helpers.

Contains pure functions that don't depend on Flask app context or content store.
"""

PRODUCTION_COMPANY_NAME = 'Open Mic Odyssey Productions'


def _build_cast_people(
    credits_people: list[dict[str, object]],
    people: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    cast_entries: list[dict[str, object]] = []
    cast_by_name: dict[str, dict[str, object]] = {}

    for credit in credits_people:
        if not isinstance(credit, dict):
            continue

        name = str(credit.get('name') or '').strip()
        if not name:
            continue

        role = str(credit.get('role') or '').strip()
        person = people.get(name, {}) if isinstance(people, dict) else {}
        description = str(person.get('credit_note') or '').strip()

        entry = cast_by_name.get(name)
        if entry is None:
            entry = {
                'name': name,
                'roles': [],
                'description': description,
            }
            cast_by_name[name] = entry
            cast_entries.append(entry)
        elif not entry['description'] and description:
            entry['description'] = description

        if role and role not in entry['roles']:
            entry['roles'].append(role)

    return cast_entries
