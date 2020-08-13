import sqlite3
import logging

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker


CREATE_PID_TABLE_QUERY = """
    CREATE TABLE IF NOT EXISTS pid_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        v2 VARCHAR(23),
        v3 VARCHAR(255),
        UNIQUE(v2, v3)
    );
"""


Base = declarative_base()


class PidVersion(Base):
    __tablename__ = 'pid_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    v2 = Column(String(23))
    v3 = Column(String(255))
    __table_args__ = (
        UniqueConstraint('v2', 'v3', name='_v2_v3_uc'),
    )

    def __repr__(self):
        return '<PidVersion(v2="%s", v3="%s")>' % (self.v2, self.v3)


class PIDVersionsManager:
    def __init__(self, db):
        self.db = db
        self.db.cursor.execute(CREATE_PID_TABLE_QUERY)
        self.engine = create_engine("dbname")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def register(self, v2, v3):
        self.session = self.Session()
        self.session.add(PidVersion(v2=v2, v3=v3))
        try:
            self.session.commit()
        except:
            logging.debug("this item already exists in database")
            self.session.rollback()
            return False
        else:
            return True

    def get_pid_v3(self, v2):
        self.session = self.Session()
        pid_register = self.session.query(PidVersion).filter_by(v2=v2).first()
        if pid_register:
            return pid_register.v3

    def pids_already_registered(self, v2, v3):
        """Verifica se a chave composta (v2 e v3) existe no banco de dadoss"""
        self.session = self.Session()
        return self.session.query(PidVersion).filter_by(v2=v2, v3=v3).count() == 1

    def close(self):
        self.__exit__()


class PIDVersionsDB:
    def __init__(self, name, timeout=60):
        try:
            self.conn = sqlite3.connect(name, timeout=timeout)
            self.cursor = self.conn.cursor()
        except sqlite3.OperationalError as e:
            logging.exception(e)
            raise sqlite3.OperationalError("unable to open database '%s'" % name)

    def close(self):
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, excution_type, excution_value, traceback):

        if isinstance(excution_value, Exception):
            self.conn.rollback()
        else:
            self.conn.commit()

        self.close()

    def fetch(self, sql, parameters=None):
        self.cursor.execute(sql, parameters)
        return self.cursor.fetchall()

    def insert(self, sql, parameters):
        try:
            self.cursor.execute(sql, parameters)
        except sqlite3.IntegrityError as e:
            logging.debug("this item already exists in database")
            return False
        else:
            self.conn.commit()
            return True

    def get_pid_v3(self, v2):
        found = self.fetch("SELECT v3 FROM pid_versions WHERE v2 = ?", (v2,))

        if found is not None and len(found) > 0:
            return found[0][0]
