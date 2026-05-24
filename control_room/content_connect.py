from flask import redirect, render_template, url_for
from .admin_utils import (
    _social_from_form,
    _link_from_form,
    _benefit_from_form,
    _tier_from_form,
)
from shared.content_store import ContentReadError, ContentWriteError, get_content_reader, get_content_writer
from .content_common import _ctx
from shared.utils import process_list_action


def _connect_admin_state():
    reader = get_content_reader()
    writer = get_content_writer()

    social_payload = reader.read('social.json')
    connect_payload = reader.read('connect.json')

    social = social_payload.get('social', [])
    if not isinstance(social, list):
        social = []

    connect = connect_payload.get('connect', {})
    links = connect.get('links', {})
    campaigns = links.get('campaigns', [])
    if not isinstance(campaigns, list):
        campaigns = []
    channels = links.get('channels', [])
    if not isinstance(channels, list):
        channels = []
    page = connect.get('page', {})
    if not isinstance(page, dict):
        page = {}
    benefits = page.get('benefits', [])
    if not isinstance(benefits, list):
        benefits = []
    tiers = page.get('tiers', [])
    if not isinstance(tiers, list):
        tiers = []

    return {
        'reader': reader,
        'writer': writer,
        'social_payload': social_payload,
        'connect_payload': connect_payload,
        'social': social,
        'campaigns': campaigns,
        'channels': channels,
        'page': page,
        'benefits': benefits,
        'tiers': tiers,
        'connect': connect,
    }


def _render_connect_template(template_name, save_error, save_success, state):

    return render_template(
        template_name,
        save_error=save_error,
        save_success=save_success,
        social=state['social'],
        campaigns=state['campaigns'],
        channels=state['channels'],
        page=state['page'],
        benefits=state['benefits'],
        tiers=state['tiers'],
        **_ctx(),
    )


def _render_connect_read_error(template_name, exc):

    return render_template(
        template_name,
        save_error=str(exc),
        save_success=False,
        social=[],
        campaigns=[],
        channels=[],
        page={},
        benefits=[],
        tiers=[],
        **_ctx(),
    )


def _handle_connect_social_request(request):

    template_name = 'connect_social.html'

    try:
        state = _connect_admin_state()
    except ContentReadError as exc:
        return _render_connect_read_error(template_name, exc)

    writer = state['writer']
    social_payload = state['social_payload']
    social = state['social']

    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'add_social':
            entry, err = _social_from_form(request.form, prefix='social_')
            if err:
                save_error = err
            else:
                social_payload['social'] = list(social) + [entry]
                try:
                    writer.write('social.json', social_payload)
                    return redirect(url_for('content.edit_connect_social', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_social':
            try:
                idx = int(request.form.get('social_index', ''))
                updated = list(social)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    social_payload['social'] = updated
                    writer.write('social.json', social_payload)
                    return redirect(url_for('content.edit_connect_social', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action == 'update_social':
            try:
                idx = int(request.form.get('social_index', ''))
                entry, err = _social_from_form(request.form, prefix='social_')
                if err:
                    save_error = err
                else:
                    updated = list(social)
                    if 0 <= idx < len(updated):
                        updated[idx] = entry
                        social_payload['social'] = updated
                        writer.write('social.json', social_payload)
                        return redirect(url_for('content.edit_connect_social', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action in {'move_up_social', 'move_down_social'}:
            try:
                mapped_action = 'move_up' if action == 'move_up_social' else 'move_down'
                updated = process_list_action(
                    social,
                    mapped_action,
                    request.form.get('social_index', '').strip(),
                )
                social_payload['social'] = updated
                writer.write('social.json', social_payload)
                return redirect(url_for('content.edit_connect_social', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1'
    )
    return _render_connect_template(template_name, save_error, save_success, state)


def _handle_connect_supporters_request(request):

    template_name = 'connect_supporters.html'

    try:
        state = _connect_admin_state()
    except ContentReadError as exc:
        return _render_connect_read_error(template_name, exc)

    writer = state['writer']
    connect = state['connect']
    connect_payload = state['connect_payload']
    campaigns = state['campaigns']
    channels = state['channels']
    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'add_campaign':
            entry, err = _link_from_form(request.form, prefix='campaign_')
            if err:
                save_error = err
            else:
                updated = list(campaigns) + [entry]
                connect.setdefault('links', {})['campaigns'] = updated
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_supporters', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_campaign':
            try:
                idx = int(request.form.get('campaign_index', ''))
                updated = list(campaigns)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    connect.setdefault('links', {})['campaigns'] = updated
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_supporters', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action == 'update_campaign':
            try:
                idx = int(request.form.get('campaign_index', ''))
                entry, err = _link_from_form(request.form, prefix='campaign_')
                if err:
                    save_error = err
                else:
                    updated = list(campaigns)
                    if 0 <= idx < len(updated):
                        updated[idx] = entry
                        connect.setdefault('links', {})['campaigns'] = updated
                        connect_payload['connect'] = connect
                        writer.write('connect.json', connect_payload)
                        return redirect(url_for('content.edit_connect_supporters', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action in {'move_up_campaign', 'move_down_campaign'}:
            try:
                mapped_action = 'move_up' if action == 'move_up_campaign' else 'move_down'
                updated = process_list_action(
                    campaigns,
                    mapped_action,
                    request.form.get('campaign_index', '').strip(),
                )
                connect.setdefault('links', {})['campaigns'] = updated
                connect_payload['connect'] = connect
                writer.write('connect.json', connect_payload)
                return redirect(url_for('content.edit_connect_supporters', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

        elif action == 'add_supporter':
            entry, err = _link_from_form(request.form, prefix='supporter_')
            if err:
                save_error = err
            else:
                updated = list(channels) + [entry]
                connect.setdefault('links', {})['channels'] = updated
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_supporters', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_supporter':
            try:
                idx = int(request.form.get('supporter_index', ''))
                updated = list(channels)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    connect.setdefault('links', {})['channels'] = updated
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_supporters', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action == 'update_supporter':
            try:
                idx = int(request.form.get('supporter_index', ''))
                entry, err = _link_from_form(request.form, prefix='supporter_')
                if err:
                    save_error = err
                else:
                    updated = list(channels)
                    if 0 <= idx < len(updated):
                        updated[idx] = entry
                        connect.setdefault('links', {})['channels'] = updated
                        connect_payload['connect'] = connect
                        writer.write('connect.json', connect_payload)
                        return redirect(url_for('content.edit_connect_supporters', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action in {'move_up_supporter', 'move_down_supporter'}:
            try:
                mapped_action = 'move_up' if action == 'move_up_supporter' else 'move_down'
                updated = process_list_action(
                    channels,
                    mapped_action,
                    request.form.get('supporter_index', '').strip(),
                )
                connect.setdefault('links', {})['channels'] = updated
                connect_payload['connect'] = connect
                writer.write('connect.json', connect_payload)
                return redirect(url_for('content.edit_connect_supporters', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1'
    )
    return _render_connect_template(template_name, save_error, save_success, state)


def _handle_connect_patreon_request(request):

    template_name = 'connect_patreon.html'

    try:
        state = _connect_admin_state()
    except ContentReadError as exc:
        return _render_connect_read_error(template_name, exc)

    writer = state['writer']
    connect = state['connect']
    connect_payload = state['connect_payload']
    page = state['page']
    benefits = state['benefits']
    tiers = state['tiers']
    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'save_page':
            page['title'] = request.form.get('page_title', '').strip()
            page['intro'] = request.form.get('page_intro', '').strip()
            page['membership_pitch'] = request.form.get(
                'page_membership_pitch', '').strip()
            page.setdefault('primary_link', {})['label'] = request.form.get(
                'page_primary_label', '').strip()
            page['primary_link']['url'] = request.form.get(
                'page_primary_url', '').strip()
            page.setdefault('secondary_link', {})['label'] = request.form.get(
                'page_secondary_label', '').strip()
            page['secondary_link']['url'] = request.form.get(
                'page_secondary_url', '').strip()
            connect['page'] = page
            connect_payload['connect'] = connect
            try:
                writer.write('connect.json', connect_payload)
                return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

        elif action == 'add_benefit':
            entry, err = _benefit_from_form(request.form, prefix='benefit_')
            if err:
                save_error = err
            else:
                page['benefits'] = list(benefits) + [entry]
                connect['page'] = page
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_patreon', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_benefit':
            try:
                idx = int(request.form.get('benefit_index', ''))
                updated = list(benefits)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    page['benefits'] = updated
                    connect['page'] = page
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action == 'update_benefit':
            try:
                idx = int(request.form.get('benefit_index', ''))
                entry, err = _benefit_from_form(
                    request.form, prefix='benefit_')
                if err:
                    save_error = err
                else:
                    updated = list(benefits)
                    if 0 <= idx < len(updated):
                        updated[idx] = entry
                        page['benefits'] = updated
                        connect['page'] = page
                        connect_payload['connect'] = connect
                        writer.write('connect.json', connect_payload)
                        return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action in {'move_up_benefit', 'move_down_benefit'}:
            try:
                mapped_action = 'move_up' if action == 'move_up_benefit' else 'move_down'
                updated = process_list_action(
                    benefits,
                    mapped_action,
                    request.form.get('benefit_index', '').strip(),
                )
                page['benefits'] = updated
                connect['page'] = page
                connect_payload['connect'] = connect
                writer.write('connect.json', connect_payload)
                return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

        elif action == 'add_tier':
            entry, err = _tier_from_form(
                request.form, prefix='tier_')
            if err:
                save_error = err
            else:
                page['tiers'] = list(tiers) + [entry]
                connect['page'] = page
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_patreon', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_tier':
            try:
                idx = int(request.form.get('tier_index', ''))
                updated = list(tiers)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    page['tiers'] = updated
                    connect['page'] = page
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action == 'update_tier':
            try:
                idx = int(request.form.get('tier_index', ''))
                entry, err = _tier_from_form(
                    request.form, prefix='tier_')
                if err:
                    save_error = err
                else:
                    updated = list(tiers)
                    if 0 <= idx < len(updated):
                        updated[idx] = entry
                        page['tiers'] = updated
                        connect['page'] = page
                        connect_payload['connect'] = connect
                        writer.write('connect.json', connect_payload)
                        return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        elif action in {'move_up_tier', 'move_down_tier'}:
            try:
                mapped_action = 'move_up' if action == 'move_up_tier' else 'move_down'
                updated = process_list_action(
                    tiers,
                    mapped_action,
                    request.form.get('tier_index', '').strip(),
                )
                page['tiers'] = updated
                connect['page'] = page
                connect_payload['connect'] = connect
                writer.write('connect.json', connect_payload)
                return redirect(url_for('content.edit_connect_patreon', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1'
    )
    return _render_connect_template(template_name, save_error, save_success, state)


def _handle_connect_request(request):
    return redirect(url_for('content.edit_connect_social'))
