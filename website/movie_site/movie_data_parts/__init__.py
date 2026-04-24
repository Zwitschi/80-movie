import json
import os


def get_movie_data():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

    movie = {}

    # Load movies.json
    with open(os.path.join(data_dir, 'movies.json'), 'r') as f:
        movies_data = json.load(f)
        movie.update(movies_data['movie'])

    # Load people.json
    with open(os.path.join(data_dir, 'people.json'), 'r') as f:
        people_data = json.load(f)
        movie['people'] = people_data['people']

    # Load organizations.json
    with open(os.path.join(data_dir, 'organizations.json'), 'r') as f:
        org_data = json.load(f)
        movie['organizations'] = org_data['organizations']

    # Load media_assets.json
    with open(os.path.join(data_dir, 'media_assets.json'), 'r') as f:
        media_data = json.load(f)
        movie.update(media_data['media'])

    # Load events.json
    with open(os.path.join(data_dir, 'events.json'), 'r') as f:
        events_data = json.load(f)
        movie['screenings'] = events_data['events']

    # Load reviews.json
    with open(os.path.join(data_dir, 'reviews.json'), 'r') as f:
        reviews_data = json.load(f)
        movie.update(reviews_data)

    # Load offers.json
    with open(os.path.join(data_dir, 'offers.json'), 'r') as f:
        offers_data = json.load(f)
        movie.update(offers_data)

    # Load faq.json
    with open(os.path.join(data_dir, 'faq.json'), 'r') as f:
        faq_data = json.load(f)
        movie['faq_items'] = faq_data['faq']

    # Load gallery.json
    with open(os.path.join(data_dir, 'gallery.json'), 'r') as f:
        gallery_data = json.load(f)
        movie['gallery_items'] = gallery_data['gallery']

    # Load social.json
    with open(os.path.join(data_dir, 'social.json'), 'r') as f:
        social_data = json.load(f)
        movie['social_links'] = social_data['social']

    # Load support.json
    with open(os.path.join(data_dir, 'support.json'), 'r') as f:
        support_data = json.load(f)
        movie['support_links'] = support_data['support']['links']
        movie['supporter_page'] = support_data['support']['page']

    # Set production_company from organizations
    movie['production_company'] = org_data['organizations']['Open Mic Odyssey Productions']

    # Add contributors and credits_people from people
    # For now, manually add based on old structure
    movie['contributors'] = {
        'directors': [{'name': 'Open Mic Odyssey Team', 'job_title': 'Director', 'url': 'https://openmicodyssey.com', 'same_as': ['https://openmicodyssey.com'], 'credit_note': 'Shapes the documentary point of view and guides the on-the-road narrative structure.'}],
        'producers': [
            {'name': 'Open Mic Odyssey Team', 'job_title': 'Producer', 'url': 'https://openmicodyssey.com', 'same_as': [
                'https://openmicodyssey.com'], 'credit_note': 'Coordinates production, release planning, and how the film reaches audiences.'},
            {'name': 'Georg Sinn', 'job_title': 'Producer', 'url': 'https://allucanget.biz',
                'credit_note': 'Infrastructure, logistics, IT, development, finance.'}
        ],
        'actors': [
            {'name': 'Bobby Ludlam', 'job_title': 'Self',
                'credit_note': 'One of the three best friends at the heart of the documentary, a comedian chasing stage time and a bigger creative dream.'},
            {'name': 'Corey Pellizzi', 'job_title': 'Self',
                'credit_note': 'Directing, filming, and drawn to places of his childhood, creativity and freedom.'},
            {'name': 'Georg Sinn', 'job_title': 'Self',
                'credit_note': 'From far away, driving across America and keeping the crew rolling toward the next place to film, perform, and connect with the comedy world.'}
        ]
    }
    movie['credits_people'] = [
        {'name': 'Bobby Ludlam', 'roles': ['Comedian', 'Security']},
        {'name': 'Corey Pellizzi', 'roles': [
            'Comedian', 'Director', 'Producer', 'Security']},
        {'name': 'Georg Sinn', 'roles': [
            'Manager', 'Driver', 'Traveler', 'Security']}
    ]

    return movie


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
        'release_status': movie['release_status'],
        'current_year': current_year,
    }
