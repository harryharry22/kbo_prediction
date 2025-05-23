from flask import Flask, request, jsonify
from flask_apscheduler import APScheduler
from database import db
import crawler
import data_processor
import predictor
from datetime import datetime
from models import WinProbability, RankingPredict
import os

# 스케줄러 인스턴스 생성
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)

    # Flask-APScheduler 설정
    app.config['SCHEDULER_API_ENABLED'] = True

    # MySQL 연결 정보 (환경 변수 사용 권장)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DB_URI',
        'mysql+pymysql://root:dugout2025!!@dugout-dev.cn6mm486utfi.ap-northeast-2.rds.amazonaws.com:3306/dugoutDB?charset=utf8'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 확장 기능 초기화
    db.init_app(app)
    scheduler.init_app(app)

    # 스케줄러 작업 등록 및 시작
    scheduler.start()

    # 캐시 데이터 초기화
    app.cached_data = {
        'hitter_data': None,
        'pitcher_data': None,
        'win_probability_df': None,
        'last_update': None
    }

    # 매일 00:00 KST에 실행되는 작업
    @scheduler.task('cron', id='daily_update', hour=0, minute=0, timezone='Asia/Seoul')
    def daily_data_update():
        with app.app_context():  # 앱 컨텍스트 보장
            print("🔁 자정 강제 데이터 갱신 시작...")
            try:
                # 데이터 수집
                hitter_data = crawler.crawl_hitter_data()
                pitcher_data = crawler.crawl_pitcher_data()
                hist_hitter, hist_pitcher = crawler.load_historical_data()

                # 데이터 처리
                processed_hitter = data_processor.process_hitter_data(hitter_data, hist_hitter)
                processed_pitcher = data_processor.process_pitcher_data(pitcher_data, hist_pitcher)

                # DB 갱신
                predictor.generate_win_probability_df(processed_hitter, processed_pitcher)

                # 캐시 초기화
                app.cached_data.update({
                    'hitter_data': processed_hitter,
                    'pitcher_data': processed_pitcher,
                    'last_update': datetime.now(),
                    'win_probability_df': predictor.get_win_probability_df(app.cached_data)
                })
                print("✅ 자동 갱신 완료!")
            except Exception as e:
                print(f"⚠️ 자동 갱신 실패: {str(e)}")

    # --- 여기서부터 라우트 정의 ---

    @app.route('/')
    def home():
        return "KBO 야구 승률 예측 API. '/predict_win_rate' 엔드포인트를 사용하세요."

    @app.route('/predict_win_rate', methods=['POST'])
    def predict_win_rate():
        data = request.get_json()
        if not data or 'team1' not in data or 'team2' not in data:
            return jsonify({'error': '두 팀 이름을 제공해야 합니다. 예: {"team1": "LG", "team2": "삼성"}'}), 400

        team1 = data['team1']
        team2 = data['team2']

        try:
            win_probability_df = predictor.get_win_probability_df(app.cached_data)
            valid_teams = win_probability_df.index.tolist()

            if team1 not in valid_teams:
                return jsonify({'error': f"'{team1}'은(는) 유효한 팀 이름이 아닙니다. 유효한 팀 목록: {', '.join(valid_teams)}"}), 400
            if team2 not in valid_teams:
                return jsonify({'error': f"'{team2}'은(는) 유효한 팀 이름이 아닙니다. 유효한 팀 목록: {', '.join(valid_teams)}"}), 400
            if team1 == team2:
                return jsonify({'error': "같은 팀 간의 승률은 계산할 수 없습니다."}), 400

            win_prob = win_probability_df.loc[team1, team2]
            if win_prob == '-':
                return jsonify({'error': "승률을 계산할 수 없습니다."}), 400

            return jsonify({
                'team1': team1,
                'team2': team2,
                'win_probability': float(win_prob),
                'message': f"{team1}이(가) {team2}을(를) 상대로 승리할 예측 승률은 {win_prob}% 입니다."
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/historical_data', methods=['GET'])
    def get_historical_data():
        try:
            records = WinProbability.query.all()
            result = [{
                'team1': r.team1,
                'team2': r.team2,
                'probability': r.probability,
                'date': r.created_date.strftime('%Y-%m-%d %H:%M:%S')
            } for r in records]
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/ranking', methods=['GET'])
    def get_ranking():
        try:
            latest_date = db.session.query(db.func.max(RankingPredict.created_date)).scalar()
            records = RankingPredict.query.filter_by(created_date=latest_date).all()

            result = [{
                'team': r.team,
                'rank': r.rank,
                'avg_win_prob': r.avg_win_prob,
                'date': r.created_date.strftime('%Y-%m-%d %H:%M:%S')
            } for r in records]

            return jsonify(sorted(result, key=lambda x: x['rank']))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # --- force-update 엔드포인트 추가 ---
    @app.route('/force-update', methods=['POST'])
    def force_update():
        try:
            scheduler.run_job('daily_update')
            return jsonify({"status": "Job triggered successfully"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app

# 앱 생성 및 실행
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080)
