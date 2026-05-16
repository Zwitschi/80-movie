from .db import get_conn


class DbContentReader:
    def read(self, filename: str):
        # This will be implemented to read from the database
        pass

    def read_all(self) -> dict:
        # This will be implemented to read all content from the database
        pass


class DbContentWriter:
    def write(self, filename: str, payload) -> None:
        # This will be implemented to write to the database
        pass


def get_content_reader() -> DbContentReader:
    return DbContentReader()


def get_content_writer() -> DbContentWriter:
    return DbContentWriter()
