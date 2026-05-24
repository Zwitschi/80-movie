from flask import redirect, render_template, url_for
from .admin_utils import _contributor_from_form, _credit_from_form, _person_from_form, _org_from_form, CONTRIBUTOR_SECTIONS
from shared.utils import (
    load_json,
    save_json,
    process_list_action,
)
from .content_common import _ctx


def _render_people_form(*, save_error, save_success, people, contributors, credits_people, organizations, page_context):
    return render_template(
        'people.html',
        save_error=save_error,
        save_success=save_success,
        people=people,
        contributors=contributors,
        credits_people=credits_people,
        organizations=organizations,
        contributor_sections=CONTRIBUTOR_SECTIONS,
        **page_context,
    )


def _handle_people_request(request):
    people_payload = load_json('people.json')
    orgs_payload = load_json('organizations.json')

    people = people_payload.get('people', {})
    if not isinstance(people, dict):
        people = {}
    contributors = people_payload.get('contributors', {})
    if not isinstance(contributors, dict):
        contributors = {}
    credits_people = people_payload.get('credits_people', [])
    if not isinstance(credits_people, list):
        credits_people = []
    organizations = orgs_payload.get('organizations', {})
    if not isinstance(organizations, dict):
        organizations = {}

    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'add_person':
            entry, err = _person_from_form(
                request.form, prefix='person_')
            if err:
                save_error = err
            else:
                people = dict(people)
                people[entry['name']] = entry
                people_payload['people'] = people
                success, save_error = save_json(
                    'people.json', people_payload)
                if success:
                    return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'remove_person':
            key = request.form.get('person_key', '').strip()
            if key in people:
                people = dict(people)
                del people[key]
                people_payload['people'] = people
                success, save_error = save_json(
                    'people.json', people_payload)
                if success:
                    return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'add_contributor':
            section = request.form.get(
                'contributor_section', '').strip().lower()
            if section not in CONTRIBUTOR_SECTIONS:
                save_error = f'Invalid contributor section: {section!r}.'
            else:
                entry, err = _contributor_from_form(
                    request.form,
                    prefix='contributor_',
                )
                if err:
                    save_error = err
                else:
                    contributors = dict(contributors)
                    contributors[section] = process_list_action(
                        contributors.get(section, []),
                        'add',
                        '',
                        entry,
                    )
                    people_payload['contributors'] = contributors
                    success, save_error = save_json(
                        'people.json', people_payload)
                    if success:
                        return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'remove_contributor':
            section = request.form.get(
                'contributor_section', '').strip().lower()
            idx_str = request.form.get('contributor_index', '')
            contributors = dict(contributors)
            contributors[section] = process_list_action(
                contributors.get(section, []),
                'remove',
                idx_str,
            )
            people_payload['contributors'] = contributors
            success, save_error = save_json(
                'people.json', people_payload)
            if success:
                return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'add_credit':
            entry, err = _credit_from_form(
                request.form, prefix='credit_')
            if err:
                save_error = err
            else:
                credits_people = process_list_action(
                    credits_people,
                    'add',
                    '',
                    entry,
                )
                people_payload['credits_people'] = credits_people
                success, save_error = save_json(
                    'people.json', people_payload)
                if success:
                    return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'remove_credit':
            credits_people = process_list_action(
                credits_people,
                'remove',
                request.form.get('credit_index', ''),
            )
            people_payload['credits_people'] = credits_people
            success, save_error = save_json(
                'people.json', people_payload)
            if success:
                return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'add_org':
            entry, err = _org_from_form(
                request.form, prefix='org_')
            if err:
                save_error = err
            else:
                organizations = dict(organizations)
                organizations[entry['name']] = entry
                orgs_payload['organizations'] = organizations
                success, save_error = save_json(
                    'organizations.json', orgs_payload)
                if success:
                    return redirect(url_for('content.edit_people', saved='1'))

        elif action == 'remove_org':
            key = request.form.get('org_key', '').strip()
            if key in organizations:
                organizations = dict(organizations)
                del organizations[key]
                orgs_payload['organizations'] = organizations
                success, save_error = save_json(
                    'organizations.json', orgs_payload)
                if success:
                    return redirect(url_for('content.edit_people', saved='1'))

    save_success = (save_error is None and request.method ==
                    'POST') or (request.args.get('saved') == '1')
    return _render_people_form(
        save_error=save_error,
        save_success=save_success,
        people=people,
        contributors=contributors,
        credits_people=credits_people,
        organizations=organizations,
        page_context=_ctx(),
    )
