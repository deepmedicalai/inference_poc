
import redis
from rq import Queue, Connection
from flask import render_template, Blueprint, jsonify, request, current_app
from webserver import get_db, query_db, upsert_db, delete_db
from webserver.security import validate_edge_token
from tasks.edge_transfer import create_new_session
from tasks.stages import get_session_status


api_blueprint = Blueprint('api', __name__,)

@api_blueprint.route('/api/health', methods=['GET'])
def health():
    db_conn = get_db()
    row = query_db(db_conn, 'SELECT COUNT(*) as cnt from sessions', one=True)
    session_cnt = row['cnt']

    response_object = {
        'status': 'success',
        'sessions': session_cnt
    }
    return jsonify(response_object), 200


@api_blueprint.route('/api/session/start', methods=['POST'])
def start_process():

    db_conn = get_db()
    new_session_info = create_new_session(db_conn, current_app.config)

    return jsonify({ 'success': True, 'session_id':new_session_info['id'], 'subdir':new_session_info['subdir']})

@api_blueprint.route('/api/session/status/<session_id>', methods=['GET'])
def check_session_status(session_id):
    try:
        db_conn = get_db()
        session_info = get_session_status(db_conn, int(session_id))
        if session_info is not None:
            return jsonify({'status':True, 'info':session_info}),200
        else:
            return jsonify({'status':False, 'reason':'not found'}), 404
    except Exception as e:
        current_app.logger.error(e) 
        return jsonify({ 'status': False, 'exception':True}), 400
   