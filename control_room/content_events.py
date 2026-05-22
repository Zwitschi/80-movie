from flask import redirect, render_template, url_for


def _render_events_form(*, save_error, save_success, events, offers, page_context):
    from . import admin_content

    return render_template(
        'admin/events.html',
        save_error=save_error,
        save_success=save_success,
        events=events,
        offers=offers,
        event_statuses=admin_content.EVENT_STATUSES,
        event_attendance_modes=admin_content.EVENT_ATTENDANCE_MODES,
        offer_availabilities=admin_content.OFFER_AVAILABILITIES,
        **page_context,
    )


def _handle_events_request(request):
    from . import admin_content

    events_payload = admin_content.load_json('events.json')
    offers_payload = admin_content.load_json('offers.json')
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
            events = admin_content.process_list_action(
                events,
                'remove',
                request.form.get('event_index', ''),
            )
            events_payload['events'] = events
            success, err = admin_content.save_json('events.json', events_payload)
            if success:
                return redirect(url_for('content.edit_events', saved='1'))
            save_error = err

        elif action == 'remove_offer':
            offers = admin_content.process_list_action(
                offers,
                'remove',
                request.form.get('offer_index', ''),
            )
            offers_payload['offers'] = offers
            success, err = admin_content.save_json('offers.json', offers_payload)
            if success:
                return redirect(url_for('content.edit_events', saved='1'))
            save_error = err

        elif action == 'add_event':
            new_event, err = admin_content._event_from_form(request.form)
            if err:
                save_error = err
            else:
                events = admin_content.process_list_action(events, 'add', '', new_event)
                events_payload['events'] = events
                success, err = admin_content.save_json('events.json', events_payload)
                if success:
                    return redirect(url_for('content.edit_events', saved='1'))
                save_error = err

        elif action == 'add_offer':
            new_offer, err = admin_content._offer_from_form(request.form)
            if err:
                save_error = err
            else:
                offers = admin_content.process_list_action(offers, 'add', '', new_offer)
                offers_payload['offers'] = offers
                success, err = admin_content.save_json('offers.json', offers_payload)
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
        page_context=admin_content._ctx(),
    )