from flask import redirect, render_template, url_for
from .admin_utils import (
    _event_from_form,
    _offer_from_form,
)

from shared.utils import (
    load_content,
    save_content,
    process_list_action,
    EVENT_STATUSES,
    EVENT_ATTENDANCE_MODES,
    OFFER_AVAILABILITIES,

)
from .content_common import _ctx


def _render_events_form(*, save_error, save_success, events, offers, page_context,
                        edit_event=None, edit_index=''):
    return render_template(
        'events.html',
        save_error=save_error,
        save_success=save_success,
        events=events,
        offers=offers,
        event_statuses=EVENT_STATUSES,
        event_attendance_modes=EVENT_ATTENDANCE_MODES,
        offer_availabilities=OFFER_AVAILABILITIES,
        edit_event=edit_event,
        edit_index=edit_index,
        **page_context,
    )


def _handle_events_request(request):
    events_payload = load_content('events')
    offers_payload = load_content('offers')
    events = events_payload.get('events', [])
    if not isinstance(events, list):
        events = []
    offers = offers_payload.get('offers', [])
    if not isinstance(offers, list):
        offers = []

    save_error = None
    save_success = False

    edit_index = request.args.get('edit_event', '')

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'remove_event':
            events = process_list_action(
                events,
                'remove',
                request.form.get('event_index', ''),
            )
            events_payload['events'] = events
            success, err = save_content(
                'events', events_payload)
            if success:
                return redirect(url_for('content.edit_events', saved='1'))
            save_error = err

        elif action == 'remove_offer':
            offers = process_list_action(
                offers,
                'remove',
                request.form.get('offer_index', ''),
            )
            offers_payload['offers'] = offers
            success, err = save_content(
                'offers', offers_payload)
            if success:
                return redirect(url_for('content.edit_events', saved='1'))
            save_error = err

        elif action == 'add_event':
            new_event, err = _event_from_form(request.form)
            if err:
                save_error = err
            else:
                events = process_list_action(
                    events, 'add', '', new_event)
                events_payload['events'] = events
                success, err = save_content(
                    'events', events_payload)
                if success:
                    return redirect(url_for('content.edit_events', saved='1'))
                save_error = err

        elif action == 'update_event':
            new_event, err = _event_from_form(request.form)
            if err:
                save_error = err
            else:
                edit_idx_str = request.form.get('edit_index', '')
                try:
                    idx = int(edit_idx_str)
                    if 0 <= idx < len(events):
                        events[idx] = new_event
                        events_payload['events'] = events
                        success, err = save_content('events', events_payload)
                        if success:
                            return redirect(url_for('content.edit_events', saved='1'))
                        save_error = err
                    else:
                        save_error = 'Invalid event index.'
                except ValueError:
                    save_error = 'Invalid event index.'

        elif action == 'add_offer':
            new_offer, err = _offer_from_form(request.form)
            if err:
                save_error = err
            else:
                offers = process_list_action(
                    offers, 'add', '', new_offer)
                offers_payload['offers'] = offers
                success, err = save_content(
                    'offers', offers_payload)
                if success:
                    return redirect(url_for('content.edit_events', saved='1'))
                save_error = err

        if save_error is None:
            save_success = True

    save_success = save_success or (request.args.get('saved') == '1')

    edit_event = None
    if edit_index:
        try:
            idx = int(edit_index)
            if 0 <= idx < len(events):
                edit_event = events[idx]
        except ValueError:
            pass

    return _render_events_form(
        save_error=save_error,
        save_success=save_success,
        events=events,
        offers=offers,
        edit_event=edit_event,
        edit_index=edit_index,
        page_context=_ctx(),
    )
