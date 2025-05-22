from datetime import datetime
from database import db

class WinProbability(db.Model):
    __tablename__ = 'win_probability'
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(20), nullable=False)
    team2 = db.Column(db.String(20), nullable=False)
    probability = db.Column(db.Float, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 업데이트 시 시간 갱신

    __table_args__ = (
        db.UniqueConstraint('team1', 'team2', name='unique_team_pair'),
        {'extend_existing': True}
    )


class RankingPredict(db.Model):
    __tablename__ = 'ranking_predict'
    id = db.Column(db.Integer, primary_key=True)
    team = db.Column(db.String(20), nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    avg_win_prob = db.Column(db.Float, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('team', 'created_date', name='unique_team_date'),
        {'extend_existing': True}
    )

class HitterRecord(db.Model):
    __tablename__ = 'hitter_record'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    선수명 = db.Column(db.String(50))
    팀명 = db.Column(db.String(20))
    연도 = db.Column(db.Integer)
    AVG = db.Column(db.Float)
    G = db.Column(db.Integer)
    PA = db.Column(db.Integer)
    AB = db.Column(db.Integer)
    R = db.Column(db.Integer)
    H = db.Column(db.Integer)
    _2B = db.Column('2B', db.Integer)  # 숫자로 시작하는 컬럼명 처리
    _3B = db.Column('3B', db.Integer)
    HR = db.Column(db.Integer)
    TB = db.Column(db.Integer)
    RBI = db.Column(db.Integer)
    SAC = db.Column(db.Integer)
    SF = db.Column(db.Integer)
    OPS_predict = db.Column(db.Float)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

class PitcherRecord(db.Model):
    __tablename__ = 'pitcher_record'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    선수명 = db.Column(db.String(50))
    팀명 = db.Column(db.String(20))
    연도 = db.Column(db.Integer)
    ERA = db.Column(db.Float)
    G = db.Column(db.Integer)
    W = db.Column(db.Integer)
    L = db.Column(db.Integer)
    SV = db.Column(db.Integer)
    HLD = db.Column(db.Integer)
    WPCT = db.Column(db.Float)
    IP = db.Column(db.Float)
    H = db.Column(db.Integer)
    HR = db.Column(db.Integer)
    BB = db.Column(db.Integer)
    HBP = db.Column(db.Integer)
    SO = db.Column(db.Integer)
    R = db.Column(db.Integer)
    ER = db.Column(db.Integer)
    WHIP = db.Column(db.Float)
    WHIP_predict = db.Column(db.Float)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
