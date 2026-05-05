import json

import pytest

from website.app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _patch_admin_content_store(data_dir):
    from website.movie_site import admin as admin_module
    from website.movie_site import utils as utils_module
    from website.movie_site.content_store import JsonContentReader, JsonContentWriter

    admin_module.get_content_reader = lambda: JsonContentReader(
        data_dir=data_dir)
    admin_module.get_content_writer = lambda: JsonContentWriter(
        data_dir=data_dir)
    utils_module.get_content_reader = lambda: JsonContentReader(
        data_dir=data_dir)
    utils_module.get_content_writer = lambda: JsonContentWriter(
        data_dir=data_dir)


def test_admin_film_get_renders_form(client):
    response = client.get('/admin/film')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Edit Film Details' in body
    assert 'name="title"' in body
    assert 'Save Film Details' in body


def test_admin_film_post_updates_movies_json(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    movies_path = data_dir / 'movies.json'
    original_payload = {
        'movie': {
            'title': 'Old Title',
            'tagline': 'Old Tagline',
            'description': 'Old Description',
            'genre': 'Documentary',
            'keywords': ['x'],
            'runtime': '120 min',
            'duration_iso': 'PT120M',
            'release_date': 'TBD',
            'release_status': {
                'label': 'Old Label',
                'headline': 'Old Headline',
                'summary': 'Old Summary',
                'detail': 'Old Detail',
            },
        }
    }
    movies_path.write_text(json.dumps(
        original_payload, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/film',
        data={
            'title': 'New Title',
            'tagline': 'New Tagline',
            'description': 'New Description',
            'genre': 'Doc',
            'runtime': '124 min',
            'duration_iso': 'PT124M',
            'release_date': '2026-08-01',
            'release_status_label': 'Now',
            'release_status_headline': 'Headline',
            'release_status_summary': 'Summary',
            'release_status_detail': 'Detail',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/film?saved=1' in response.headers['Location']

    updated_payload = json.loads(movies_path.read_text(encoding='utf-8'))
    movie = updated_payload['movie']
    assert movie['title'] == 'New Title'
    assert movie['tagline'] == 'New Tagline'
    assert movie['description'] == 'New Description'
    assert movie['genre'] == 'Doc'
    assert movie['runtime'] == '124 min'
    assert movie['duration_iso'] == 'PT124M'
    assert movie['release_date'] == '2026-08-01'
    assert movie['release_status']['label'] == 'Now'


def test_admin_media_get_lists_gallery_items(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    gallery_path = data_dir / 'gallery.json'
    gallery_payload = {
        'gallery': [
            {
                'title': 'Sample Still',
                'category': 'Still',
                'image_url': 'https://example.com/still.jpg',
                'alt': 'Still frame',
                'description': 'Test item',
            }
        ]
    }
    gallery_path.write_text(json.dumps(
        gallery_payload, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/media')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Manage Media Gallery' in body
    assert 'Sample Still' in body
    assert 'Add Gallery Item' in body


def test_admin_media_post_add_updates_gallery_json(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    gallery_path = data_dir / 'gallery.json'
    gallery_path.write_text(json.dumps(
        {'gallery': []}, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/media',
        data={
            'action': 'add',
            'title': 'New Gallery Item',
            'category': 'Poster',
            'image_url': 'https://example.com/poster.jpg',
            'alt': 'Poster alt',
            'description': 'Poster description',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/media?saved=1' in response.headers['Location']

    updated_payload = json.loads(gallery_path.read_text(encoding='utf-8'))
    assert len(updated_payload['gallery']) == 1
    assert updated_payload['gallery'][0]['title'] == 'New Gallery Item'


def test_admin_media_post_remove_updates_gallery_json(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    gallery_path = data_dir / 'gallery.json'
    gallery_payload = {
        'gallery': [
            {
                'title': 'Item A',
                'category': 'Still',
                'image_url': 'https://example.com/a.jpg',
                'alt': 'A',
                'description': 'A item',
            },
            {
                'title': 'Item B',
                'category': 'Still',
                'image_url': 'https://example.com/b.jpg',
                'alt': 'B',
                'description': 'B item',
            },
        ]
    }
    gallery_path.write_text(json.dumps(
        gallery_payload, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/media',
        data={
            'action': 'remove',
            'index': '0',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/media?saved=1' in response.headers['Location']

    updated_payload = json.loads(gallery_path.read_text(encoding='utf-8'))
    assert len(updated_payload['gallery']) == 1
    assert updated_payload['gallery'][0]['title'] == 'Item B'


def test_admin_content_get_renders_preview_and_form(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    content_path = data_dir / 'content.json'
    content_payload = {
        'pages': {
            'index': {'title': 'Overview', 'description': 'Index desc', 'keywords': ['a'], 'path': '/'},
            'film': {'title': 'Film', 'description': 'Film desc', 'keywords': ['b'], 'path': '/film'},
            'media': {'title': 'Media', 'description': 'Media desc', 'keywords': ['c'], 'path': '/media'},
            'connect': {'title': 'Connect', 'description': 'Connect desc', 'keywords': ['d'], 'path': '/connect'},
            'patreon': {'title': 'Supporters', 'description': 'Supporters desc', 'keywords': ['e'], 'path': '/patreon'},
        }
    }
    content_path.write_text(json.dumps(
        content_payload, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/content')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Edit Metadata & Copy' in body
    assert 'Read-only Preview' in body
    assert 'Generated title' in body
    assert 'name="index_title"' in body


def test_admin_content_post_updates_content_json(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    content_path = data_dir / 'content.json'
    content_payload = {
        'pages': {
            'index': {'title': 'Overview', 'description': 'Index desc', 'keywords': ['a'], 'path': '/'},
            'film': {'title': 'Film', 'description': 'Film desc', 'keywords': ['b'], 'path': '/film'},
            'media': {'title': 'Media', 'description': 'Media desc', 'keywords': ['c'], 'path': '/media'},
            'connect': {'title': 'Connect', 'description': 'Connect desc', 'keywords': ['d'], 'path': '/connect'},
            'patreon': {'title': 'Supporters', 'description': 'Supporters desc', 'keywords': ['e'], 'path': '/patreon'},
        }
    }
    content_path.write_text(json.dumps(
        content_payload, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/content',
        data={
            'index_title': 'Overview Updated',
            'index_description': 'Index desc updated',
            'index_keywords': 'x, y',
            'index_path': '/',
            'film_title': 'Film',
            'film_description': 'Film desc',
            'film_keywords': 'f1,f2',
            'film_path': '/film',
            'media_title': 'Media',
            'media_description': 'Media desc',
            'media_keywords': 'm1,m2',
            'media_path': '/media',
            'connect_title': 'Connect',
            'connect_description': 'Connect desc',
            'connect_keywords': 'c1,c2',
            'connect_path': '/connect',
            'patreon_title': 'Supporters',
            'patreon_description': 'Supporters desc',
            'patreon_keywords': 'p1,p2',
            'patreon_path': '/patreon',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/content?saved=1' in response.headers['Location']

    updated = json.loads(content_path.read_text(encoding='utf-8'))
    assert updated['pages']['index']['title'] == 'Overview Updated'
    assert updated['pages']['index']['keywords'] == ['x', 'y']


def test_admin_content_post_validates_required_fields(tmp_path, app):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    content_path = data_dir / 'content.json'
    content_payload = {
        'pages': {
            'index': {'title': 'Overview', 'description': 'Index desc', 'keywords': ['a'], 'path': '/'},
            'film': {'title': 'Film', 'description': 'Film desc', 'keywords': ['b'], 'path': '/film'},
            'media': {'title': 'Media', 'description': 'Media desc', 'keywords': ['c'], 'path': '/media'},
            'connect': {'title': 'Connect', 'description': 'Connect desc', 'keywords': ['d'], 'path': '/connect'},
            'patreon': {'title': 'Supporters', 'description': 'Supporters desc', 'keywords': ['e'], 'path': '/patreon'},
        }
    }
    content_path.write_text(json.dumps(
        content_payload, indent=2) + '\n', encoding='utf-8')

    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/content',
        data={
            'index_title': '',
            'index_description': 'Index desc updated',
            'index_keywords': 'x, y',
            'index_path': '/',
            'film_title': 'Film',
            'film_description': 'Film desc',
            'film_keywords': 'f1,f2',
            'film_path': '/film',
            'media_title': 'Media',
            'media_description': 'Media desc',
            'media_keywords': 'm1,m2',
            'media_path': '/media',
            'connect_title': 'Connect',
            'connect_description': 'Connect desc',
            'connect_keywords': 'c1,c2',
            'connect_path': '/connect',
            'patreon_title': 'Supporters',
            'patreon_description': 'Supporters desc',
            'patreon_keywords': 'p1,p2',
            'patreon_path': '/patreon',
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Missing required value: index.title' in body


def _make_events_data_dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir(exist_ok=True)
    events_payload = {
        'events': [
            {
                'name': 'Preview Screening',
                'description': 'A preview',
                'start_date': '2026-06-12T19:00:00-07:00',
                'end_date': '2026-06-12T21:30:00-07:00',
                'event_status': 'https://schema.org/EventScheduled',
                'event_attendance_mode': 'https://schema.org/OfflineEventAttendanceMode',
                'location': {
                    'name': 'Test Venue',
                    'url': 'https://example.com',
                    'address': {
                        'street_address': '123 Main St',
                        'address_locality': 'Los Angeles',
                        'address_region': 'CA',
                        'postal_code': '90001',
                        'address_country': 'US',
                    },
                },
                'video_format': 'HD',
                'subtitle_language': 'en',
                'offers': [],
            }
        ]
    }
    offers_payload = {
        'offers': [
            {
                'name': 'Digital waitlist',
                'url': 'https://example.com/connect',
                'category': 'Streaming access',
                'availability': 'https://schema.org/PreOrder',
                'price': 0,
                'price_currency': 'USD',
                'valid_from': '2026-04-07',
                'description': 'Join the list.',
            }
        ]
    }
    (data_dir / 'events.json').write_text(
        json.dumps(events_payload, indent=2) + '\n', encoding='utf-8')
    (data_dir / 'offers.json').write_text(
        json.dumps(offers_payload, indent=2) + '\n', encoding='utf-8')
    return data_dir


def test_admin_events_get_renders_events_and_offers(tmp_path, app):
    data_dir = _make_events_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/events')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Manage Events' in body
    assert 'Preview Screening' in body
    assert 'Digital waitlist' in body
    assert 'Add Screening' in body
    assert 'Add Offer' in body


def test_admin_events_post_add_event(tmp_path, app):
    data_dir = _make_events_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/events',
        data={
            'action': 'add_event',
            'event_name': 'New Screening',
            'event_description': 'A new screening',
            'event_start_date': '2026-09-01T18:00:00-07:00',
            'event_end_date': '2026-09-01T20:00:00-07:00',
            'event_status': 'https://schema.org/EventScheduled',
            'event_attendance_mode': 'https://schema.org/OfflineEventAttendanceMode',
            'event_location_name': 'Cinema X',
            'event_location_url': 'https://cinemax.com',
            'event_street_address': '456 Film Ave',
            'event_address_locality': 'Burbank',
            'event_address_region': 'CA',
            'event_postal_code': '91505',
            'event_address_country': 'US',
            'event_video_format': 'DCP',
            'event_subtitle_language': 'en',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/events?saved=1' in response.headers['Location']

    updated = json.loads(
        (data_dir / 'events.json').read_text(encoding='utf-8'))
    assert len(updated['events']) == 2
    assert updated['events'][1]['name'] == 'New Screening'
    assert updated['events'][1]['location']['name'] == 'Cinema X'


def test_admin_events_post_remove_event(tmp_path, app):
    data_dir = _make_events_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/events',
        data={'action': 'remove_event', 'event_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'events.json').read_text(encoding='utf-8'))
    assert updated['events'] == []


def test_admin_events_post_add_offer(tmp_path, app):
    data_dir = _make_events_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/events',
        data={
            'action': 'add_offer',
            'offer_name': 'Early Bird Ticket',
            'offer_url': 'https://example.com/tickets',
            'offer_category': 'Ticket',
            'offer_availability': 'https://schema.org/InStock',
            'offer_price': '12.50',
            'offer_price_currency': 'USD',
            'offer_valid_from': '2026-05-01',
            'offer_description': 'Early bird price.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/events?saved=1' in response.headers['Location']

    updated = json.loads(
        (data_dir / 'offers.json').read_text(encoding='utf-8'))
    assert len(updated['offers']) == 2
    assert updated['offers'][1]['name'] == 'Early Bird Ticket'
    assert updated['offers'][1]['price'] == 12.5


def test_admin_events_post_remove_offer(tmp_path, app):
    data_dir = _make_events_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/events',
        data={'action': 'remove_offer', 'offer_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'offers.json').read_text(encoding='utf-8'))
    assert updated['offers'] == []


def test_admin_events_post_validates_date_format(tmp_path, app):
    data_dir = _make_events_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/events',
        data={
            'action': 'add_event',
            'event_name': 'Bad Date Event',
            'event_start_date': '2026/06/12 19:00',
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Invalid start_date format' in body


def _make_faq_data_dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir(exist_ok=True)
    faq_payload = {
        'faq': [
            {'question': 'What is this?', 'answer': 'A documentary film.'},
            {'question': 'Is there a trailer?', 'answer': 'Yes, see the site.'},
        ]
    }
    (data_dir / 'faq.json').write_text(
        json.dumps(faq_payload, indent=2) + '\n', encoding='utf-8')
    return data_dir


def test_admin_faq_get_renders_entries(tmp_path, app):
    data_dir = _make_faq_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/faq')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Manage FAQ' in body
    assert 'What is this?' in body
    assert 'Is there a trailer?' in body
    assert 'Add FAQ Entry' in body


def test_admin_faq_post_add_entry(tmp_path, app):
    data_dir = _make_faq_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/faq',
        data={
            'action': 'add',
            'question': 'When does it release?',
            'answer': 'Coming soon.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/faq?saved=1' in response.headers['Location']

    updated = json.loads((data_dir / 'faq.json').read_text(encoding='utf-8'))
    assert len(updated['faq']) == 3
    assert updated['faq'][2]['question'] == 'When does it release?'


def test_admin_faq_post_remove_entry(tmp_path, app):
    data_dir = _make_faq_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/faq',
        data={'action': 'remove', 'index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads((data_dir / 'faq.json').read_text(encoding='utf-8'))
    assert len(updated['faq']) == 1
    assert updated['faq'][0]['question'] == 'Is there a trailer?'


def test_admin_faq_post_move_up(tmp_path, app):
    data_dir = _make_faq_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/faq',
        data={'action': 'move_up', 'index': '1'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads((data_dir / 'faq.json').read_text(encoding='utf-8'))
    assert updated['faq'][0]['question'] == 'Is there a trailer?'
    assert updated['faq'][1]['question'] == 'What is this?'


def test_admin_faq_post_move_down(tmp_path, app):
    data_dir = _make_faq_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/faq',
        data={'action': 'move_down', 'index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads((data_dir / 'faq.json').read_text(encoding='utf-8'))
    assert updated['faq'][0]['question'] == 'Is there a trailer?'
    assert updated['faq'][1]['question'] == 'What is this?'


def test_admin_faq_post_add_validates_required_fields(tmp_path, app):
    data_dir = _make_faq_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/faq',
        data={'action': 'add', 'question': '', 'answer': 'Some answer'},
        follow_redirects=False,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Question is required' in body


def _make_people_data_dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir(exist_ok=True)
    people_payload = {
        'people': {
            'Alice': {
                'name': 'Alice',
                'url': 'https://alice.example.com',
                'same_as': ['https://alice.example.com'],
                'roles': ['Director'],
                'job_title': 'Director',
                'credit_note': 'Lead director.',
            }
        },
        'contributors': {
            'directors': [
                {
                    'name': 'Alice',
                    'job_title': 'Director',
                    'url': 'https://alice.example.com',
                    'same_as': ['https://alice.example.com'],
                    'credit_note': 'Lead director.',
                }
            ],
            'producers': [],
            'actors': [],
        },
        'credits_people': [
            {
                'name': 'Alice',
                'roles': ['Director'],
                'primary_url': 'https://alice.example.com',
                'same_as': ['https://alice.example.com'],
            }
        ],
    }
    orgs_payload = {
        'organizations': {
            'Example Productions': {
                'name': 'Example Productions',
                'url': 'https://example.com',
                'same_as': ['https://example.com'],
                'people': ['Alice'],
            }
        }
    }
    (data_dir / 'people.json').write_text(
        json.dumps(people_payload, indent=2) + '\n', encoding='utf-8')
    (data_dir / 'organizations.json').write_text(
        json.dumps(orgs_payload, indent=2) + '\n', encoding='utf-8')
    return data_dir


def test_admin_people_get_renders_all_sections(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/people')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Manage People' in body
    assert 'Alice' in body
    assert 'Example Productions' in body
    assert 'Add Person' in body
    assert 'Add Organization' in body


def test_admin_people_post_add_person(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={
            'action': 'add_person',
            'person_name': 'Bob',
            'person_job_title': 'Producer',
            'person_roles': 'Producer, Driver',
            'person_url': 'https://bob.example.com',
            'person_same_as': 'https://bob.example.com, https://bob2.example.com',
            'person_credit_note': 'Bob runs the show.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/people?saved=1' in response.headers['Location']

    updated = json.loads(
        (data_dir / 'people.json').read_text(encoding='utf-8'))
    assert 'Bob' in updated['people']
    assert updated['people']['Bob']['roles'] == ['Producer', 'Driver']
    assert updated['people']['Bob']['same_as'] == [
        'https://bob.example.com', 'https://bob2.example.com']


def test_admin_people_post_remove_person(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={'action': 'remove_person', 'person_key': 'Alice'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'people.json').read_text(encoding='utf-8'))
    assert 'Alice' not in updated['people']


def test_admin_people_post_add_contributor(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={
            'action': 'add_contributor',
            'contributor_section': 'producers',
            'contributor_name': 'Carol',
            'contributor_job_title': 'Producer',
            'contributor_url': 'https://carol.example.com',
            'contributor_same_as': 'https://carol.example.com',
            'contributor_credit_note': 'Handles production.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'people.json').read_text(encoding='utf-8'))
    assert len(updated['contributors']['producers']) == 1
    assert updated['contributors']['producers'][0]['name'] == 'Carol'


def test_admin_people_post_remove_contributor(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={
            'action': 'remove_contributor',
            'contributor_section': 'directors',
            'contributor_index': '0',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'people.json').read_text(encoding='utf-8'))
    assert updated['contributors']['directors'] == []


def test_admin_people_post_add_credit(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={
            'action': 'add_credit',
            'credit_name': 'Dave',
            'credit_roles': 'Editor, Colorist',
            'credit_primary_url': 'https://dave.example.com',
            'credit_same_as': 'https://dave.example.com',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'people.json').read_text(encoding='utf-8'))
    assert len(updated['credits_people']) == 2
    assert updated['credits_people'][1]['name'] == 'Dave'
    assert updated['credits_people'][1]['roles'] == ['Editor', 'Colorist']


def test_admin_people_post_remove_credit(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={'action': 'remove_credit', 'credit_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'people.json').read_text(encoding='utf-8'))
    assert updated['credits_people'] == []


def test_admin_people_post_add_org(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={
            'action': 'add_org',
            'org_name': 'New Studio',
            'org_url': 'https://newstudio.example.com',
            'org_same_as': 'https://newstudio.example.com',
            'org_people': 'Alice, Bob',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/people?saved=1' in response.headers['Location']

    updated = json.loads(
        (data_dir / 'organizations.json').read_text(encoding='utf-8'))
    assert 'New Studio' in updated['organizations']
    assert updated['organizations']['New Studio']['people'] == ['Alice', 'Bob']


def test_admin_people_post_remove_org(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={'action': 'remove_org', 'org_key': 'Example Productions'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'organizations.json').read_text(encoding='utf-8'))
    assert 'Example Productions' not in updated['organizations']


def test_admin_people_post_add_person_validates_name(tmp_path, app):
    data_dir = _make_people_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/people',
        data={'action': 'add_person', 'person_name': ''},
        follow_redirects=False,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Name is required' in body


def _make_connect_data_dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir(exist_ok=True)
    social_payload = {
        'social': [
            {'label': 'Instagram', 'url': 'https://instagram.com/x',
                'description': 'Insta'},
        ]
    }
    connect_payload = {
        'connect': {
            'links': {
                'campaigns': [
                    {'label': 'Site', 'url': 'https://example.com',
                        'status': 'Live', 'description': 'Main site'}
                ],
                'supporters': [
                    {'label': 'Patreon', 'url': 'https://patreon.com/x',
                        'status': 'Support', 'description': 'Patreon page'}
                ],
            },
            'page': {
                'title': 'Support Us',
                'intro': 'Join the journey.',
                'membership_pitch': 'Back us on Patreon.',
                'primary_link': {'label': 'Join', 'url': 'https://patreon.com/x'},
                'secondary_link': {'label': 'Connect', 'url': 'https://example.com/connect'},
                'benefits': [
                    {'title': 'Early access', 'description': 'See it first.'}
                ],
                'tiers': [
                    {'name': 'Supporter', 'price': '$5/mo',
                        'description': 'Basic tier.'}
                ],
            },
        }
    }
    (data_dir / 'social.json').write_text(
        json.dumps(social_payload, indent=2) + '\n', encoding='utf-8')
    (data_dir / 'connect.json').write_text(
        json.dumps(connect_payload, indent=2) + '\n', encoding='utf-8')
    return data_dir


def test_admin_connect_get_renders_all_sections(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/connect')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Social, Connect' in body
    assert 'Instagram' in body
    assert 'Patreon' in body
    assert 'Early access' in body
    assert 'Supporter' in body
    assert 'Save Page Copy' in body


def test_admin_connect_post_add_social(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={
            'action': 'add_social',
            'social_label': 'TikTok',
            'social_url': 'https://tiktok.com/@x',
            'social_description': 'TikTok page',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/connect?saved=1' in response.headers['Location']
    updated = json.loads(
        (data_dir / 'social.json').read_text(encoding='utf-8'))
    assert len(updated['social']) == 2
    assert updated['social'][1]['label'] == 'TikTok'


def test_admin_connect_post_remove_social(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={'action': 'remove_social', 'social_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'social.json').read_text(encoding='utf-8'))
    assert updated['social'] == []


def test_admin_connect_post_add_campaign(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={
            'action': 'add_campaign',
            'campaign_label': 'Kickstarter',
            'campaign_url': 'https://kickstarter.com/x',
            'campaign_status': 'Active',
            'campaign_description': 'Crowdfund.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'connect.json').read_text(encoding='utf-8'))
    campaigns = updated['connect']['links']['campaigns']
    assert len(campaigns) == 2
    assert campaigns[1]['label'] == 'Kickstarter'


def test_admin_connect_post_remove_supporter(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={'action': 'remove_supporter', 'supporter_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'connect.json').read_text(encoding='utf-8'))
    assert updated['connect']['links']['supporters'] == []


def test_admin_connect_post_save_page(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={
            'action': 'save_page',
            'page_title': 'New Title',
            'page_intro': 'New intro.',
            'page_membership_pitch': 'New pitch.',
            'page_primary_label': 'Join Now',
            'page_primary_url': 'https://patreon.com/x',
            'page_secondary_label': 'Learn More',
            'page_secondary_url': 'https://example.com',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'connect.json').read_text(encoding='utf-8'))
    page = updated['connect']['page']
    assert page['title'] == 'New Title'
    assert page['intro'] == 'New intro.'
    assert page['primary_link']['label'] == 'Join Now'


def test_admin_connect_post_add_benefit(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={
            'action': 'add_benefit',
            'benefit_title': 'Bonus Content',
            'benefit_description': 'Extra videos.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'connect.json').read_text(encoding='utf-8'))
    benefits = updated['connect']['page']['benefits']
    assert len(benefits) == 2
    assert benefits[1]['title'] == 'Bonus Content'


def test_admin_connect_post_add_tier(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={
            'action': 'add_tier',
            'tier_name': 'Producer Circle',
            'tier_price': '$25/mo',
            'tier_description': 'Top tier.',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'connect.json').read_text(encoding='utf-8'))
    tiers = updated['connect']['page']['tiers']
    assert len(tiers) == 2
    assert tiers[1]['name'] == 'Producer Circle'


def test_admin_connect_post_remove_tier(tmp_path, app):
    data_dir = _make_connect_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/connect',
        data={'action': 'remove_tier', 'tier_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'connect.json').read_text(encoding='utf-8'))
    assert updated['connect']['page']['tiers'] == []


def _make_media_assets_data_dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir(exist_ok=True)
    payload = {
        'media': {
            'date_published': None,
            'in_language': 'en',
            'content_rating': 'Not yet rated',
            'contact_email': 'test@example.com',
            'poster_image': 'https://example.com/poster.jpg',
            'trailer': {
                'name': 'Official Trailer',
                'description': 'Watch the trailer.',
                'url': 'https://example.com/',
                'embed_url': 'https://www.youtube.com/embed/XXXXX',
                'thumbnail_url': 'https://example.com/thumb.jpg',
                'upload_date': '2026-03-15T12:00:00Z',
                'duration_iso': 'PT2M18S',
                'encoding_format': 'video/mp4',
                'is_family_friendly': True,
            },
        }
    }
    (data_dir / 'media_assets.json').write_text(
        json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return data_dir


def test_admin_media_assets_get_renders_form(tmp_path, app):
    data_dir = _make_media_assets_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/media-assets')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Media Assets' in body
    assert 'poster_image' in body
    assert 'trailer_embed_url' in body
    assert 'Preview trailer embed' in body


def test_admin_media_assets_post_save_media(tmp_path, app):
    data_dir = _make_media_assets_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/media-assets',
        data={
            'action': 'save_media',
            'poster_image': 'https://example.com/new_poster.jpg',
            'content_rating': 'PG',
            'in_language': 'en',
            'contact_email': 'new@example.com',
            'date_published': '2026-09-01',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/media-assets?saved=1' in response.headers['Location']

    updated = json.loads(
        (data_dir / 'media_assets.json').read_text(encoding='utf-8'))
    assert updated['media']['poster_image'] == 'https://example.com/new_poster.jpg'
    assert updated['media']['content_rating'] == 'PG'
    assert updated['media']['date_published'] == '2026-09-01'
    assert updated['media']['contact_email'] == 'new@example.com'


def test_admin_media_assets_post_save_trailer(tmp_path, app):
    data_dir = _make_media_assets_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/media-assets',
        data={
            'action': 'save_trailer',
            'trailer_name': 'New Trailer Name',
            'trailer_description': 'Updated description.',
            'trailer_url': 'https://example.com/trailer',
            'trailer_embed_url': 'https://www.youtube.com/embed/NEWID',
            'trailer_thumbnail_url': 'https://example.com/new_thumb.jpg',
            'trailer_upload_date': '2026-04-01T10:00:00Z',
            'trailer_duration_iso': 'PT3M00S',
            'trailer_encoding_format': 'video/mp4',
            'trailer_is_family_friendly': '1',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'media_assets.json').read_text(encoding='utf-8'))
    trailer = updated['media']['trailer']
    assert trailer['name'] == 'New Trailer Name'
    assert trailer['embed_url'] == 'https://www.youtube.com/embed/NEWID'
    assert trailer['duration_iso'] == 'PT3M00S'
    assert trailer['is_family_friendly'] is True


def test_admin_media_assets_post_save_media_clears_empty_poster(tmp_path, app):
    data_dir = _make_media_assets_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/media-assets',
        data={
            'action': 'save_media',
            'poster_image': '',
            'content_rating': 'PG',
            'in_language': 'en',
            'contact_email': 'test@example.com',
            'date_published': '',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'media_assets.json').read_text(encoding='utf-8'))
    assert updated['media']['poster_image'] is None
    assert updated['media']['date_published'] is None


def _make_reviews_data_dir(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir(exist_ok=True)
    payload = {
        'reviews': [
            {
                'author_name': 'Test Critic',
                'author_url': 'https://example.com/critic',
                'date_published': '2026-03-20',
                'name': 'Great film',
                'review_body': 'A wonderful documentary.',
                'review_rating': 4.5,
            }
        ],
        'aggregate_rating': {
            'rating_value': 4.5,
            'best_rating': 5,
            'worst_rating': 1,
            'rating_count': 10,
            'review_count': 3,
        },
    }
    (data_dir / 'reviews.json').write_text(
        json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return data_dir


def test_admin_reviews_get_renders_form(tmp_path, app):
    data_dir = _make_reviews_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.get('/admin/reviews')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Manage Reviews' in body
    assert 'Test Critic' in body
    assert 'agg_rating_value' in body


def test_admin_reviews_post_add_review(tmp_path, app):
    data_dir = _make_reviews_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/reviews',
        data={
            'action': 'add_review',
            'review_author_name': 'New Reviewer',
            'review_author_url': 'https://reviewer.example.com',
            'review_name': 'Brilliant',
            'review_review_body': 'An outstanding film.',
            'review_review_rating': '5.0',
            'review_date_published': '2026-04-01',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert '/admin/reviews?saved=1' in response.headers['Location']
    updated = json.loads(
        (data_dir / 'reviews.json').read_text(encoding='utf-8'))
    assert len(updated['reviews']) == 2
    assert updated['reviews'][1]['author_name'] == 'New Reviewer'
    assert updated['reviews'][1]['review_rating'] == 5.0


def test_admin_reviews_post_remove_review(tmp_path, app):
    data_dir = _make_reviews_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/reviews',
        data={'action': 'remove_review', 'review_index': '0'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'reviews.json').read_text(encoding='utf-8'))
    assert updated['reviews'] == []


def test_admin_reviews_post_save_aggregate(tmp_path, app):
    data_dir = _make_reviews_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/reviews',
        data={
            'action': 'save_aggregate',
            'agg_rating_value': '4.8',
            'agg_best_rating': '5',
            'agg_worst_rating': '1',
            'agg_rating_count': '50',
            'agg_review_count': '12',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = json.loads(
        (data_dir / 'reviews.json').read_text(encoding='utf-8'))
    agg = updated['aggregate_rating']
    assert agg['rating_value'] == 4.8
    assert agg['rating_count'] == 50
    assert agg['review_count'] == 12


def test_admin_reviews_post_add_review_validates_rating_bounds(tmp_path, app):
    data_dir = _make_reviews_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/reviews',
        data={
            'action': 'add_review',
            'review_author_name': 'Critic',
            'review_review_body': 'Some text.',
            'review_review_rating': '7',
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'review_rating must be between 0 and 5' in body


def test_admin_reviews_post_save_aggregate_validates_bounds(tmp_path, app):
    data_dir = _make_reviews_data_dir(tmp_path)
    _patch_admin_content_store(data_dir)

    client = app.test_client()
    response = client.post(
        '/admin/reviews',
        data={
            'action': 'save_aggregate',
            'agg_rating_value': '4.8',
            'agg_best_rating': '1',
            'agg_worst_rating': '5',
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert 'best_rating must not be less than worst_rating' in body
