from datetime import datetime
from database import db  # 변경된 임포트

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
