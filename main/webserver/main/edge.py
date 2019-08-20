
from flask import render_template, Blueprint, jsonify, request, current_app
from webserver import get_db, query_db, upsert_db, delete_db
from webserver.security import validate_edge_token
from tasks.edge_transfer import get_session_for_edge, acknowledge_file, edge_completed_transfer


edge_blueprint = Blueprint('edge', __name__,)

@edge_blueprint.route('/edge/readyfortransfer', methods=['GET'])
def readyfortransfer():
    try: 

        validated, token = validate_edge_token(request)
        if not validated:
            return jsonify({"message": "ERROR: Unauthorized"}), 401

        db_conn = get_db()
        session_id = get_session_for_edge(db_conn)

        if session_id is not None:
            return jsonify({ 'ready': True, 'session_id':session_id}) 

        return jsonify({ 'ready': False, 'reason':'not started'})
    except Exception as e:
        current_app.logger.error(e) 
        return jsonify({ 'ready': False, 'exception':True}), 400


@edge_blueprint.route('/edge/statusupdate/<session_id>', methods=['POST'])
def edge_statusupdate(session_id):
    try:

        validated, token = validate_edge_token(request)
        if not validated:
            return jsonify({"message": "ERROR: Unauthorized"}), 401

        content = request.json 
        file_name = content['file_name']
        file_path = content['file_path']
        session_id_int = int(session_id)
        db_conn = get_db()

        file_info = acknowledge_file(db_conn, session_id_int, file_name, file_path, current_app.config)

        if file_info is not None:

            #TODO: add to queue for processing

            return jsonify({"session_id":session_id, "status":"ack", "count":file_info['count']}), 200

        #app.logger.warning('edge notified:'+ jsonify(content))
        return jsonify({"session_id":session_id, "status":"failed"}), 400
    except Exception as e:
        current_app.logger.error(e)
        return jsonify({ 'ready': False, 'exception':True}), 400

@edge_blueprint.route('/edge/transfercomplete/<session_id>', methods=['POST'])
def edge_statusupdatecompleted(session_id):
    try:

        validated, token = validate_edge_token(request)
        if not validated:
            return jsonify({"message": "ERROR: Unauthorized"}), 401

        db_conn = get_db()
        session_id_int = int(session_id)

        info = edge_completed_transfer(db_conn, session_id_int, current_app.config)

        if info is not None:
            return jsonify({"session_id":session_id_int, "status":"ack", "count":info['file_count']})

        #app.logger.warning('edge notified:'+ jsonify(content))
        return jsonify({"session_id":session_id_int, "status":"failed"})
    except Exception as e:
        print(e)
        current_app.logger.error(e)
        return jsonify({ 'ready': False, 'exception':True})