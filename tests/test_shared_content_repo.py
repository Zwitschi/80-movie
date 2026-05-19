from website.app import create_app
from website.movie_site.bot_content_repo import (
    ContentStoreWebsiteContentRepository,
    build_content_store_website_content_repository,
)


class FakeContentReader:
    def __init__(self, payloads):
        self._payloads = payloads

    def read(self, filename: str):
        return self._payloads.get(filename, {})


def test_content_store_website_content_repository_maps_shared_dtos():
    repository = ContentStoreWebsiteContentRepository(
        reader_factory=lambda: FakeContentReader(
            {
                'movies.json': {
                    'movie': {
                        'title': 'Open Mic Odyssey',
                        'tagline': 'Road movie',
                        'description': 'Feature documentary',
                        'genre': 'Documentary',
                        'duration_iso': 'PT93M',
                        'release_date': '2026-09-01',
                        'release_status': {
                            'label': 'In Production',
                            'headline': 'Now touring',
                            'summary': 'Festival run underway',
                        },
                    }
                },
                'media_assets.json': {'media': {'poster_image': '/static/images/poster.jpg'}},
                'events.json': {
                    'events': [
                        {
                            'name': 'Festival Premiere',
                            'description': 'First public screening',
                            'start_date': '2026-10-03',
                            'end_date': '2026-10-03',
                            'event_status': 'https://schema.org/EventScheduled',
                            'event_attendance_mode': 'https://schema.org/OfflineEventAttendanceMode',
                            'location': {
                                'name': 'Cinema 1',
                                'url': 'https://cinema.example',
                                'address': {
                                    'street_address': '123 Main St',
                                    'address_locality': 'Berlin',
                                    'address_region': 'BE',
                                    'postal_code': '10115',
                                    'address_country': 'DE',
                                },
                            },
                            'video_format': 'DCP',
                            'subtitle_language': 'en',
                            'offers': [
                                {
                                    'name': 'Tickets',
                                    'url': 'https://tickets.example',
                                    'price': 12.5,
                                    'price_currency': 'EUR',
                                    'availability': 'https://schema.org/InStock',
                                    'valid_from': '2026-08-01',
                                }
                            ],
                        }
                    ]
                },
                'connect.json': {
                    'connect': {
                        'links': {
                            'campaigns': [
                                {
                                    'label': 'Patreon',
                                    'url': 'https://patreon.example/openmic',
                                    'status': 'active',
                                    'description': 'Support the film',
                                }
                            ]
                        }
                    }
                },
            }
        )
    )

    metadata = repository.get_production_metadata()
    screenings = repository.list_screening_events()
    campaigns = repository.list_campaign_links()

    assert metadata.title == 'Open Mic Odyssey'
    assert metadata.poster_image == '/static/images/poster.jpg'
    assert metadata.release_status_label == 'In Production'
    assert len(screenings) == 1
    assert screenings[0].location_locality == 'Berlin'
    assert screenings[0].offers[0].price == 12.5
    assert len(campaigns) == 1
    assert campaigns[0].label == 'Patreon'


def test_build_content_store_website_content_repository_reads_live_content():
    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        repository = build_content_store_website_content_repository()
        metadata = repository.get_production_metadata()
        screenings = repository.list_screening_events()
        campaigns = repository.list_campaign_links()

    assert metadata.title
    assert isinstance(screenings, tuple)
    assert isinstance(campaigns, tuple)
