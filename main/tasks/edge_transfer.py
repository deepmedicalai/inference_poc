from webserver import query_db, upsert_db, delete_db
from tasks.stages import SESSION_STAGE_TO_INDEX, SESSION_STAGE, FILE_STAGE_TO_INDEX, FILE_STAGE
from tasks.relevance import prepare_for_relevance
from tasks.pipline import prepare_files
import redis
from flask import current_app
from rq import Queue, Connection
import random
from datetime import datetime
import os


SESSION_MIN_ID = 10000
SESSION_MAX_ID = 99999


def is_unique_session_id(db_conn, session_id_proposed):
    result = query_db(db_conn, 'SELECT id from sessions where id = ? LIMIT 1 ', [session_id_proposed], one=True)
    return result is None

def generate_session_id(db_conn):
    #possible to refactor to generate sequential session
    return random.randint(SESSION_MIN_ID, SESSION_MAX_ID)

def get_incoming_dir_for_session(session_id, config):
    incoming_path = config['INCOMING_DIR']
    relative_session_dir = './'+str(session_id)
    session_dir = os.path.join(incoming_path, relative_session_dir)
    return session_dir, relative_session_dir

def create_new_session(db_conn, config):
    session_id_proposed = -1
    while True:
        session_id_proposed = generate_session_id(db_conn)
        if is_unique_session_id(db_conn, session_id_proposed):
            break

    #session_id_proposed is unique
    session_dir, relative_dir = get_incoming_dir_for_session(session_id_proposed, config)
    #create new directory
    os.mkdir(session_dir)

    upsert_db(db_conn
    , 'INSERT INTO sessions (id, stage, file_count, begin_date, end_date) VALUES (?,?,?,?,Null)'
    , [session_id_proposed, SESSION_STAGE_TO_INDEX['started'], 0, datetime.utcnow().isoformat()])

    new_session_info = {}
    new_session_info['id'] = session_id_proposed
    new_session_info['subdir'] = relative_dir

    return new_session_info

def get_session_for_edge(db_conn):
    session_id = -1
    row = query_db(db_conn, 'SELECT id from sessions where stage = ? ORDER BY begin_date DESC LIMIT 1 ', [SESSION_STAGE_TO_INDEX['started']], one=True)
    if row is None:
        return None
    
    session_id = row['id']

    return session_id

def acknowledge_file(db_conn, session_id, file_name, file_path, config):

    row = query_db(db_conn
        , 'SELECT id, file_count from sessions where id = ? and stage <= ? ORDER BY begin_date DESC LIMIT 1 '
        , [session_id, SESSION_STAGE_TO_INDEX['receiving_files_in_progress']], one=True)
    
    if row is not None:
        session_id, file_count = row['id'], row['file_count']
        file_count = file_count + 1
        file_id = session_id * 1000 + file_count

        session_stage = SESSION_STAGE_TO_INDEX['receiving_files_in_progress']
        utc_time = datetime.utcnow().isoformat()
 
        #check if files is there
        session_dir, relative_dir = get_incoming_dir_for_session(session_id, config)

        local_file_path = os.path.join(session_dir, file_path)
        if (os.path.exists(local_file_path)):
            current_app.logger.info('File is found at {}'.format(local_file_path))
        else:
            current_app.logger.info('File is not found at {}'.format(local_file_path))

        upsert_db(db_conn, 'UPDATE sessions SET stage = ?, file_count = ? WHERE id = ?', [session_stage, file_count, session_id])

        upsert_db(db_conn
        , 'INSERT INTO files (id, session_id, file_name, file_stage, initial_path, begin_date, end_date) VALUES (?,?,?,?,?,?,?)'
        , [file_id, session_id, file_name, FILE_STAGE_TO_INDEX['announced'], file_path, utc_time, utc_time])

        file_info = {}
        file_info['file_id'] = file_id
        file_info['count'] = file_count

        return file_info

    else:
        return None

def edge_completed_transfer(db_conn, session_id, config):
    row = query_db(db_conn,
        'SELECT id, file_count from sessions where id = ? and stage <= ? ORDER BY begin_date DESC LIMIT 1 '
        , [session_id, SESSION_STAGE_TO_INDEX['receiving_files_in_progress']], one=True)
    if row is not None:
        session_id, file_count = row['id'], row['file_count']
            
        session_stage = SESSION_STAGE_TO_INDEX['receiving_files_completed']
        utc_time = datetime.utcnow().isoformat()
            
        upsert_db(db_conn, 'UPDATE sessions SET stage = ? WHERE id = ?', [session_stage, session_id])
            
        with Connection(redis.from_url(config['REDIS_URL'])):
            q = Queue()
            task = q.enqueue(prepare_files, session_id)
            current_app.logger.info('Task scheduled for prepare_files({})'.format(session_id))

        info = {}
        info['file_count'] = file_count

        return info

    return None