from flask import redirect, render_template, url_for
from .admin_utils import (
    _event_from_form,
    _offer_from_form,
)

from shared.utils import (
    load_json,
    save_json,
    process_list_action,
    EVENT_STATUSES,
    EVENT_ATTENDANCE_MODES,
    OFFER_AVAILABILITIES,

)
from .content_common import _ctx


def _render_events_form(*, save_error, save_success, events, offers, page_context):
    return render_template(
        'admin/events.html',
        save_error=save_error,
        save_success=save_success,
        events=events,
        offers=offers,
        event_statuses=EVENT_STATUSES,
        event_attendance_modes=EVENT_ATTENDANCE_MODES,
        offer_availabilities=OFFER_AVAILABILITIES,
        **page_context,
    )


def _handle_events_request(request):
    events_payload = load_json('events.json')
    offers_payload = load_json('offers.json')
    events = events_payload.get('events', [])
    if not isinstance(events, list):
        events = []
    offers = offers_payload.get('offers', [])
    if not isinstance(offers, list):
        offers = []

    save_error = None
    save_success = False

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'remove_event':
            events = process_list_action(
                events,
                'remove',
                request.form.get('event_index', ''),
            )
            events_payload['events'] = events
            success, err = save_json(
                'events.json', events_payload)
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
            success, err = save_json(
                'offers.json', offers_payload)
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
                success, err = save_json(
                    'events.json', events_payload)
                if success:
                    return redirect(url_for('content.edit_events', saved='1'))
                save_error = err

        elif action == 'add_offer':
            new_offer, err = _offer_from_form(request.form)
            if err:
                save_error = err
            else:
                offers = process_list_action(
                    offers, 'add', '', new_offer)
                offers_payload['offers'] = offers
                success, err = save_json(
                    'offers.json', offers_payload)
                if success:
                    return redirect(url_for('content.edit_events', saved='1'))
                save_error = err

        if save_error is None:
            save_success = True

    save_success = save_success or (request.args.get('saved') == '1')
    return _render_events_form(
        save_error=save_error,
        save_success=save_success,
        events=events,
        offers=offers,
        page_context=_ctx(),
    )
