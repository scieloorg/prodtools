import sqlite3
import logging

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError


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
    def __init__(self, name, timeout=None):
        engine_args = {"pool_timeout": timeout} if timeout else {}
        self.engine = create_engine(name, **engine_args)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def __enter__(self):
        return self

    def __exit__(self, excution_type, excution_value, traceback):

        if hasattr(self, "session") and self.session:
            if isinstance(excution_value, Exception):
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()

    def register(self, v2, v3):
        self.session = self.Session()
        try:
            self.session.add(PidVersion(v2=v2, v3=v3))
            self.session.commit()
        except IntegrityError:
            logging.debug("this item already exists in database")
            return True
        except Exception as e:
            self.session.rollback()
            logging.exception(
                "Error registering pids (%s, %s): %s" % (v2, v3, str(e)))
            return False
        else:
            return True

    def get_pid_v3(self, v2):
        if not v2:
            return
        self.session = self.Session()
        pid_register = self.session.query(PidVersion).filter_by(v2=v2).first()
        if pid_register:
            return pid_register.v3

    def get_records(self, v2):
        if not v2:
            return
        self.session = self.Session()
        return self.session.query(PidVersion).filter_by(v2=v2).all()

    def get_most_recent_pid_v3(self, prev_pid, pid_v2):
        prev_records = self.get_records(prev_pid) or []
        v2_records = self.get_records(pid_v2) or []
        v3_items = set([record.v3 for record in prev_records + v2_records])

        if len(v3_items) == 1:
            return v3_items.pop()
        elif len(v3_items) > 1:
            # encontrou v3 repetidos para o mesmo documento
            # considerar o mais recente record.id é o maior
            return sorted(
                        [(record.id, record.v3)
                         for record in prev_records + v2_records])[-1][1]

    def pids_already_registered(self, v2, v3):
        """Verifica se a chave composta (v2 e v3) existe no banco de dadoss"""
        self.session = self.Session()
        return self.session.query(PidVersion).filter_by(v2=v2, v3=v3).count() == 1

    def close(self):
        self.__exit__()
