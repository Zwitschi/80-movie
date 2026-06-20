"""Content API routes for screening events in bot_api.

These endpoints expose screening event CRUD via JSON for external
consumers and automated tooling, using the same content store
reader/writer as the control_room admin UI.
"""

from flask import jsonify, request
from shared.utils import load_content, save_content


def list_screenings_api():
    """GET  /api/content/screenings  — list all screening events."""
    payload = load_content('events')
    events = payload.get('events', [])
    return jsonify({'screenings': events})


def get_screening_api(index: str):
    """GET  /api/content/screenings/<index>  — single screening event."""
    try:
        idx = int(index)
    except ValueError:
        return jsonify({'error': 'Invalid index'}), 400
    payload = load_content('events')
    events = payload.get('events', [])
    if idx < 0 or idx >= len(events):
        return jsonify({'error': 'Screening not found'}), 404
    return jsonify({'screening': events[idx]})


def delete_screening_api(index: str):
    """DELETE  /api/content/screenings/<index>  — remove a screening."""
    try:
        idx = int(index)
    except ValueError:
        return jsonify({'error': 'Invalid index'}), 400
    payload = load_content('events')
    events = payload.get('events', [])
    if idx < 0 or idx >= len(events):
        return jsonify({'error': 'Screening not found'}), 404
    events.pop(idx)
    payload['events'] = events
    success, err = save_content('events', payload)
    if not success:
        return jsonify({'error': err}), 500
    return jsonify({'status': 'deleted'})


def list_offers_api():
    """GET  /api/content/offers  — list all global offers."""
    payload = load_content('offers')
    offers = payload.get('offers', [])
    return jsonify({'offers': offers})


def register_content_api_routes(bp):
    """Register content API routes on a Blueprint or Flask app."""
    bp.add_url_rule(
        '/api/content/screenings',
        view_func=list_screenings_api,
        methods=['GET'],
    )
    bp.add_url_rule(
        '/api/content/screenings/<index>',
        view_func=get_screening_api,
        methods=['GET'],
    )
    bp.add_url_rule(
        '/api/content/screenings/<index>',
        view_func=delete_screening_api,
        methods=['DELETE'],
    )
    bp.add_url_rule(
        '/api/content/offers',
        view_func=list_offers_api,
        methods=['GET'],
    )
