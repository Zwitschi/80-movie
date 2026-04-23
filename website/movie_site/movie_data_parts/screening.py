def build_screening_data():
    return {
        'screenings': [
            {
                'name': 'Open Mic Odyssey preview screening',
                'description': 'A preview screening followed by a filmmaker Q&A.',
                'start_date': '2026-06-12T19:00:00-07:00',
                'end_date': '2026-06-12T21:30:00-07:00',
                'event_status': 'https://schema.org/EventScheduled',
                'event_attendance_mode': 'https://schema.org/OfflineEventAttendanceMode',
                'location': {
                    'name': 'Digital Debris Video Gallery',
                    'url': 'https://openmicodyssey.com/screenings',
                    'address': {
                        'street_address': '2646 N Figueroa St',
                        'address_locality': 'Los Angeles',
                        'address_region': 'CA',
                        'postal_code': '90065',
                        'address_country': 'US',
                    },
                },
                'video_format': 'HD',
                'subtitle_language': 'en',
                'offers': [
                    {
                        'name': 'Preview screening ticket',
                        'url': 'https://openmicodyssey.com/tickets',
                        'price': 15,
                        'price_currency': 'USD',
                        'availability': 'https://schema.org/InStock',
                        'valid_from': '2026-04-07',
                    }
                ],
            }
        ],
    }
