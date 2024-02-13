import sqlalchemy as sq
from sqlalchemy.orm import declarative_base,  relationship


Base = declarative_base()


class Dictionary(Base):
    __tablename__ = "dictionary"
    id = sq.Column(sq.Integer, primary_key=True)
    target_word = sq.Column(sq.String(length=100))
    translate = sq.Column(sq.String(length=100))
    words_user = relationship("WordsUser", cascade="all, delete",
                               backref="dictionary")

    def __str__(self):
        return f'Dictionary {self.id}: ({self.target_word}, {self.translate})'


class WordsUser(Base):
    __tablename__ = "words_user"
    user_id = sq.Column(sq.BIGINT, primary_key=True)
    word_id = sq.Column(sq.Integer, sq.ForeignKey("dictionary.id"),
                        primary_key=True)

    def __str__(self):
        return f'WordsUser ({self.user_id}, {self.word_id})'


class WordsDel(Base):
    __tablename__ = "words_del"
    user_id = sq.Column(sq.BIGINT, primary_key=True)
    word_id = sq.Column(sq.Integer, sq.ForeignKey("dictionary.id"),
                        primary_key=True)

    def __str__(self):
        return f'WordsDel ({self.user_id}, {self.word_id})'


def create_tables_models(engine):
    #Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
