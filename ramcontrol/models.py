# -*- coding: utf-8 -*-

import sqlalchemy as sa


class Database(object):
    """Object for accessing the database."""
    _metadata = sa.MetaData()
    _languages = [u"english", u"spanish"]  # known languages
    _word_types = ["practice", "lure", "target"]  # valid options for word types
    _instruction_types = ["main", "pre_practice", "practice", "post_practice"]

    # List of experiments currently supported
    experiments = sa.Table(
        "experiments", _metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("experiment", sa.String(32), unique=True),
        sa.Column("ps4able", sa.Boolean, default=False)
    )

    # Instructions given to the subjcet
    instructions = sa.Table(
        "instructions", _metadata,
        sa.Column("experiment", sa.String(32), primary_key=True),
        sa.Column("instructions", sa.String),
        sa.Column("type", sa.Enum(*_instruction_types))
    )

    # Pool of words
    words = sa.Table(
        "words", _metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("word", sa.String(convert_unicode=True)),
        sa.Column("language", sa.Enum(*_languages), index=True),
        sa.Column("type", sa.Enum(*_word_types), index=True),
        sa.UniqueConstraint("word", "language", "type")
    )

    def __init__(self, url, debug=False):
        self.engine = sa.create_engine(url, echo=debug)
        self._metadata.create_all(bind=self.engine)

    def insert_words(self, words, type_, language="english"):
        """Insert words into the database.

        :param list words: List of unicode words.
        :param str type_: One of the valid word types ("practice", "lure", or
            "target").
        :param str language:

        """
        assert type_ in self._word_types
        assert language in self._languages

        with self.engine.connect() as conn:
            conn.execute(self.words.insert(), [{
                "word": word,
                "language": language,
                "type": type_
            } for word in words])

    def get_word_pool(self, type_, language="english"):
        """Fetch a word pool.

        :param str type_: The type of words to select (``practice``, ``lure``,
            or ``target``).
        :param str language:
        :returns: list of words

        """
        assert language in self._languages
        assert type_ in self._word_types

        with self.engine.connect() as conn:
            sel = (sa.select([self.words.c.word])
                   .where(self.words.c.language == language)
                   .where(self.words.c.type == type_))
            result = conn.execute(sel)
            return [row[0] for row in result]
