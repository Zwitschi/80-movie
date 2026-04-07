try:
    from .movie_site import create_app
except ImportError:
    from movie_site import create_app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
