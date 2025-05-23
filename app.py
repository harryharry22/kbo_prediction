from flask import Flask, request, jsonify
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from database import db
import crawler
import data_processor
import predictor
from datetime import datetime
import os
import logging

# 스케줄러 초기화 방식 변경
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    
    # MySQL 연결 설정
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DB_URI',
        'mysql+pymysql://root:dugout2025!!@dugout-dev.cn6mm486utfi.ap-northeast-2.rds.amazonaws.com:3306/dugoutDB?charset=utf8'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 스케줄러 설정 강화
    app.config['SCHEDULER_JOBSTORES'] = {
        'default': SQLAlchemyJobStore(
            url=app.config['SQLALCHEMY_DATABASE_URI'],
            engine_options={"pool_pre_ping": True}
        )
    }
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Seoul'
    app.config['SCHEDULER_API_ENABLED'] = True

    # DB 및 스케줄러 초기화
    db.init_app(app)
    scheduler.init_app(app)

    # 로깅 설정
    logging.basicConfig()
    logging.getLogger('apscheduler').setLevel(logging.DEBUG)

    # uWSGI 호환성을 위한 시작 지점 설정
    @app.after_server_start
    def start_scheduler(app):
        if not scheduler.running:
            scheduler.start()
            app.logger.info("✅ 스케줄러가 성공적으로 시작되었습니다")

    # 스케줄러 이벤트 리스너 추가
    def job_listener(event):
        if event.exception:
            app.logger.error(f"⚠️ 작업 실패: {event.exception}")
        else:
            app.logger.info(f"✅ 작업 성공: {event.job_id}")

    scheduler.add_listener(job_listener, 
        APScheduler.EVENT_JOB_EXECUTED | APScheduler.EVENT_JOB_ERROR)

    # 매일 자정 작업 등록
    @scheduler.task('cron', id='daily_update', hour=0, minute=0, misfire_grace_time=300)
    def daily_data_update():
        with app.app_context():
            app.logger.info("🔁 자정 강제 데이터 갱신 시작...")
            try:
                # 크롤링 및 데이터 처리 로직
                hitter = crawler.crawl_hitter_data()
                pitcher = crawler.crawl_pitcher_data()
                hist_hitter, hist_pitcher = crawler.load_historical_data()
                
                processed_hitter = data_processor.process_hitter_data(hitter, hist_hitter)
                processed_pitcher = data_processor.process_pitcher_data(pitcher, hist_pitcher)
                
                # DB 갱신
                predictor.generate_win_probability_df(processed_hitter, processed_pitcher)
                
                # 캐시 초기화
                app.cached_data.update({
                    'hitter_data': processed_hitter,
                    'pitcher_data': processed_pitcher,
                    'last_update': datetime.now(),
                    'win_probability_df': predictor.get_win_probability_df(app.cached_data)
                })
                app.logger.info("✅ 자동 갱신 완료!")
            except Exception as e:
                app.logger.error(f"⚠️ 자동 갱신 실패: {str(e)}")
                raise

    # 라우트 정의
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

    return app


# 앱 생성 및 실행
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080)
