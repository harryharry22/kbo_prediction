import pandas as pd
import numpy as np
import datetime
from crawler import crawl_hitter_data, crawl_pitcher_data, load_historical_data
from data_processor import process_hitter_data, process_pitcher_data
from models import WinProbability, RankingPredict
from database import db  # db는 database.py에서 import

from sqlalchemy import and_

def generate_win_probability_df(all_hitter_data, all_pitcher_data):
    """팀별 승률 및 순위 계산 후 DB 저장 (OPS - WHIP 내림차순 기준)"""
    if all_hitter_data.empty or all_pitcher_data.empty:
        raise ValueError("입력 데이터가 비어있습니다.")

    # 2025년 데이터 필터링
    df_2025_hitter = all_hitter_data[all_hitter_data['연도'] == 2025]
    df_2025_pitcher = all_pitcher_data[all_pitcher_data['연도'] == 2025]

    # 팀별 OPS/WHIP 평균
    team_ops = df_2025_hitter.groupby('팀명')['OPS_predict'].mean().reset_index()
    team_whip = df_2025_pitcher.groupby('팀명')['WHIP_predict'].mean().reset_index()

    # 데이터 병합 및 점수 계산
    victory_df = pd.merge(
        team_whip,
        team_ops,
        on='팀명'
    )
    victory_df['OPS_minus_WHIP'] = victory_df['OPS_predict'] - victory_df['WHIP_predict']
    adjustment = abs(victory_df['OPS_minus_WHIP'].min()) + 0.1
    victory_df['Adjusted_Score'] = victory_df['OPS_minus_WHIP'] + adjustment

    # 승률 매트릭스 생성
    teams = victory_df['팀명'].tolist()
    win_probability_df = pd.DataFrame(index=teams, columns=teams)

    for team_a in teams:
        score_a = victory_df[victory_df['팀명'] == team_a]['Adjusted_Score'].values[0]
        for team_b in teams:
            if team_a == team_b:
                win_probability_df.loc[team_a, team_b] = '-'
                continue
            score_b = victory_df[victory_df['팀명'] == team_b]['Adjusted_Score'].values[0]
            win_prob = (score_a / (score_a + score_b)) * 100
            win_probability_df.loc[team_a, team_b] = round(win_prob, 2)

    # 순위 계산 (OPS_minus_WHIP 내림차순)
    current_time = datetime.datetime.utcnow()
    victory_df_sorted = victory_df.sort_values('OPS_minus_WHIP', ascending=False)

    ranking_data = []
    for idx, row in victory_df_sorted.iterrows():
        ranking_data.append({
            'team': row['팀명'],
            'OPS_minus_WHIP': row['OPS_minus_WHIP']
        })

    ranking_df = pd.DataFrame(ranking_data)
    ranking_df['rank'] = ranking_df['OPS_minus_WHIP'].rank(method='min', ascending=False).astype(int)

    # DB 저장 로직
    try:
        # 기존 순위 데이터 전체 삭제
        db.session.query(RankingPredict).delete()

        # 새로운 순위 데이터 추가
        for _, row in ranking_df.iterrows():
            db.session.add(RankingPredict(
                team=row['team'],
                rank=row['rank'],
                avg_win_prob=row['OPS_minus_WHIP'],  # avg_win_prob 필드에 OPS_minus_WHIP 저장
                created_date=current_time
            ))

        # 승률 데이터 UPSERT (명시적 확인)
        for team1 in teams:
            for team2 in teams:
                prob = win_probability_df.loc[team1, team2]
                if prob != '-':
                    # 기존 데이터 조회
                    existing = db.session.query(WinProbability).filter(
                        and_(
                            WinProbability.team1 == team1,
                            WinProbability.team2 == team2
                        )
                    ).first()

                    if existing:
                        # 업데이트
                        existing.probability = float(prob)
                        existing.created_date = current_time
                    else:
                        # 새로 추가
                        db.session.add(WinProbability(
                            team1=team1,
                            team2=team2,
                            probability=float(prob),
                            created_date=current_time
                        ))

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"DB 저장 실패: {str(e)}")
    finally:
        db.session.close()

    return win_probability_df

# predictor.py 내 get_win_probability_df 함수 수정
def get_win_probability_df(cached_data):
    current_time = datetime.datetime.now()

    # 강제 업데이트 조건 (00:00~00:04)
    force_update = current_time.hour == 0 and current_time.minute < 5

    # 캐시 유효성 검사 (DataFrame 존재 여부 + empty 체크)
    win_prob_df = cached_data.get('win_probability_df')
    if (win_prob_df is None or
            (isinstance(win_prob_df, pd.DataFrame) and win_prob_df.empty) or
            force_update):
        print("🔁 데이터 새로고침 시작...")

        # 데이터 수집
        hitter = process_hitter_data(
            crawl_hitter_data(),
            load_historical_data()[0]
        )
        pitcher = process_pitcher_data(
            crawl_pitcher_data(),
            load_historical_data()[1]
        )

        # 계산 및 캐시 업데이트
        cached_data.update({
            'win_probability_df': generate_win_probability_df(hitter, pitcher),
            'last_update': current_time,
            'next_update': current_time + datetime.timedelta(hours=24)
        })

    return cached_data['win_probability_df']
