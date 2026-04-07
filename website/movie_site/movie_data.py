def get_movie_data():
    return {
        'title': 'Open Mic Odyssey',
        'tagline': 'Good Morning, I Apologize',
        'description': 'Three best friends go across America to pursue the dream...',
        'genre': 'Documentary',
        'keywords': [
            'documentary',
            'stand-up comedy',
            'road trip',
            'friendship',
            'independent film',
        ],
        'runtime': '124 min',
        'duration_iso': 'PT124M',
        'release_date': 'Coming Soon',
        'date_published': None,
        'in_language': 'en',
        'content_rating': 'Not yet rated',
        'poster_image': 'https://openmicodyssey.com/static/images/poster-placeholder.jpg',
        'trailer': {
            'name': 'Open Mic Odyssey official trailer',
            'description': 'Trailer for the documentary feature Open Mic Odyssey.',
            'url': 'https://openmicodyssey.com/trailer',
            'embed_url': 'https://www.youtube.com/embed/open-mic-odyssey-trailer',
            'thumbnail_url': 'https://openmicodyssey.com/static/images/trailer-placeholder.jpg',
            'upload_date': '2026-03-15',
            'duration_iso': 'PT2M18S',
            'encoding_format': 'video/mp4',
            'is_family_friendly': True,
        },
        'production_company': {
            'name': 'Open Mic Odyssey Productions',
            'url': 'https://openmicodyssey.com',
            'same_as': [
                'https://openmicodyssey.com',
                'https://www.youtube.com/@openmicodyssey',
                'https://www.instagram.com/openmicodyssey',
                'https://www.tiktok.com/@openmicodyssey',
                'https://www.patreon.com/openmicodyssey',
            ],
        },
        'contributors': {
            'directors': [
                {
                    'name': 'Open Mic Odyssey Team',
                    'job_title': 'Director',
                    'url': 'https://openmicodyssey.com',
                    'same_as': ['https://openmicodyssey.com'],
                    'credit_note': 'Shapes the documentary point of view and guides the on-the-road narrative structure.',
                }
            ],
            'producers': [
                {
                    'name': 'Open Mic Odyssey Team',
                    'job_title': 'Producer',
                    'url': 'https://openmicodyssey.com',
                    'same_as': ['https://openmicodyssey.com'],
                    'credit_note': 'Coordinates production, release planning, and how the film reaches audiences.',
                }
            ],
            'actors': [],
        },
        'social_links': [
            {
                'label': 'Official Website',
                'url': 'https://openmicodyssey.com',
            },
            {
                'label': 'Instagram',
                'url': 'https://www.instagram.com/openmicodyssey',
            },
            {
                'label': 'TikTok',
                'url': 'https://www.tiktok.com/@openmicodyssey',
            },
            {
                'label': 'YouTube',
                'url': 'https://www.youtube.com/@openmicodyssey',
            },
            {
                'label': 'Patreon',
                'url': 'https://www.patreon.com/openmicodyssey',
            },
        ],
        'aggregate_rating': {
            'rating_value': 4.8,
            'best_rating': 5,
            'worst_rating': 1,
            'rating_count': 24,
            'review_count': 8,
        },
        'reviews': [
            {
                'author_name': 'Festival Programming Notes',
                'author_url': 'https://openmicodyssey.com',
                'date_published': '2026-03-20',
                'name': 'A heartfelt comedy road documentary',
                'review_body': 'An intimate documentary about friendship, artistic ambition, and the grind of chasing stage time across America.',
                'review_rating': 4.8,
            }
        ],
        'screenings': [
            {
                'name': 'Open Mic Odyssey festival preview screening',
                'description': 'A preview screening followed by a filmmaker Q&A.',
                'start_date': '2026-06-12T19:00:00-05:00',
                'end_date': '2026-06-12T21:30:00-05:00',
                'event_status': 'https://schema.org/EventScheduled',
                'event_attendance_mode': 'https://schema.org/OfflineEventAttendanceMode',
                'location': {
                    'name': 'The Aurora Theater',
                    'url': 'https://openmicodyssey.com/screenings',
                    'address': {
                        'street_address': '123 Festival Ave',
                        'address_locality': 'Austin',
                        'address_region': 'TX',
                        'postal_code': '78701',
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
        'offers': [
            {
                'name': 'Digital release waitlist',
                'url': 'https://openmicodyssey.com/watch',
                'category': 'Streaming access',
                'availability': 'https://schema.org/PreOrder',
                'price': 0,
                'price_currency': 'USD',
                'valid_from': '2026-04-07',
                'description': 'Join the list for streaming and digital purchase updates.',
            }
        ],
        'faq_items': [
            {
                'question': 'What is Open Mic Odyssey about?',
                'answer': 'It follows three best friends on a cross-country run toward stand-up comedy stages and a bigger creative dream.',
            },
            {
                'question': 'Is there a trailer available?',
                'answer': 'Yes. The site links to the official trailer and will be updated with release and screening information.',
            },
        ],
    }


def get_movie_page_context(current_year):
    movie = get_movie_data()
    return {
        'movie': movie,
        'movie_title': movie['title'],
        'movie_tagline': movie['tagline'],
        'movie_description': movie['description'],
        'movie_genre': movie['genre'],
        'movie_runtime': movie['runtime'],
        'release_date': movie['release_date'],
        'current_year': current_year,
    }
