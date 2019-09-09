import time
import os
import shutil
from webserver import query_db, upsert_db, delete_db
import sqlite3
import importlib
from tasks.stages import SESSION_STAGE_TO_INDEX, SESSION_STAGE, FILE_STAGE_TO_INDEX, FILE_STAGE, set_session_stage_to, get_session_status
from dicoms.utils import (get_relevance_inference_model, get_segmentation_inference_model, get_classification_inference_model, create_frame_for_classification_internal, 
                        get_relevance_internal, get_max_of_frames_internal, get_mask_for_dicom_internal, save_mask_resized_internal, prepare_pixel_data,    
                        get_video_classification_internal)
                        
from flask import Flask
from functools import partial, reduce
from datetime import datetime
import redis
from rq import Queue, Connection
from tasks.mask import prepare_for_mask

def get_flask_config():
    # instantiate the app
    app = Flask(
        __name__, static_url_path=''
    )

    # set config
    app_settings = os.getenv('APP_SETTINGS')
    app.config.from_object(app_settings)
    return app.config


def get_db():
    config = get_flask_config()
    #db_path = os.path.join( os.path.dirname(os.getcwd()), 'main', './database/database.db')
    print('db_path', config['DATABASE'])
    db = sqlite3.connect(config['DATABASE'])
    return db

def close_connection(db):
    if db is not None:
        db.close()

def get_incoming_dir_for_session(session_id, config):
    incoming_path = config['INCOMING_DIR']
    relative_session_dir = './'+str(session_id)
    session_dir = os.path.join(incoming_path, relative_session_dir)
    return session_dir, relative_session_dir

def dbrecord_to_object_internal(row, options):
    if options['SHOW_DEBUG_MESSAGES']:
        print('dbrecord_to_object: {}'.format(row['id']))
    obj  = {}
    path = row['processing_path']
    obj['id'] = row['id']
    obj['file_id'] = obj['id']
    obj['session_id'] = row['session_id']
    obj['file_stage'] = row['file_stage']
    obj['dicom_path'] = path
    obj['base_name'] = os.path.splitext(os.path.basename(path))[0]
    obj['is_error'] = False
    obj['break_processing'] = False
    obj['is_supportedSOP'] = False

    return obj

def save_file_stage_internal(element, options, db_conn, stage):
    if options['SHOW_DEBUG_MESSAGES']:
        print('save_file_stage_internal: ', element['id'])
    file_id = element['id']
    element['file_stage'] = stage
    #get file id and relevance
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ? WHERE id = ?'
            , [element['file_stage'], file_id])
    
    return element


def save_relevance_status_internal(element, options, db_conn):

    if options['SHOW_DEBUG_MESSAGES']:
        print('save_relevance_status_internal: ', element['id'], element['relevant'])
    file_id = element['id']
    is_relevant_str = 'YES' if element['relevant'] else 'NO'
    element['file_stage'] = FILE_STAGE_TO_INDEX['has_relevance_result']
    #get file id and relevance
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, relevance_result = ? WHERE id = ?'
            , [element['file_stage'], is_relevant_str, file_id])
    
    return element


def save_max_frame_path_internal(element, options, db_conn):

    if options['SHOW_DEBUG_MESSAGES']:
        print('save_mask_path_internal: ', element['id'], element['max_frame_path'])
    file_id = element['id']
    element['file_stage'] = FILE_STAGE_TO_INDEX['has_max_frame']
    #get file id and mask_path
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, max_frame_path = ? WHERE id = ?'
            , [element['file_stage'], element['max_frame_path'], file_id])
    
    return element

def save_mask_path_internal(element, options, db_conn):

    if options['SHOW_DEBUG_MESSAGES']:
        print('save_mask_path_internal: ', element['id'], element['mask_path'])
    file_id = element['id']
    element['file_stage'] = FILE_STAGE_TO_INDEX['has_mask_result']
    #get file id and mask_path
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, mask_path = ? WHERE id = ?'
            , [element['file_stage'], element['mask_path'], file_id])
    
    return element


def save_video_classification_status_internal(element, options, db_conn):
    
    if options['SHOW_DEBUG_MESSAGES']:
        print('save_video_classification_status_internal: ', element['id'], element['classification'])
    file_id = element['id']
    result =  'Disease was detected' if element['classification_result'] else 'Healthy'
    element['file_stage'] = FILE_STAGE_TO_INDEX['ready_for_results']
    #get file id and relevance
    upsert_db(db_conn
            , 'UPDATE files SET file_stage = ?, classification_result = ? WHERE id = ?'
            , [element['file_stage'], result, file_id])
    
    return element


def prepare_files(session_id):
    print('Started \'prepare_for_relevance\' for {}'.format(session_id))
    start_dt = datetime.now()
    db_conn = get_db()

    config = get_flask_config()
    session_info = get_session_status(db_conn, session_id)
    if session_info is None:
        print('Failed to find session with id {}'.format(session_id))
        close_connection(db_conn)
        return 

    print('Working in stage {}'.format(session_info['stage_str']))
    set_session_stage_to(db_conn, session_id, SESSION_STAGE_TO_INDEX['relevance_classification_preparing_files'])
    session_info = get_session_status(db_conn, session_id)
    print('Working in stage {}'.format(session_info['stage_str']))

    move_files_to_procesing_dir(db_conn, session_id, config)

    close_connection(db_conn)

    with Connection(redis.from_url(config['REDIS_URL'])):
        q = Queue()
        task = q.enqueue(process_files, session_id)
        print('Task scheduled for process_files({})'.format(session_id))

    end_dt = datetime.now()
    delta = end_dt - start_dt
    print('prepare_for_relevance for {} took:'.format(session_id), delta)
    return True

def process_files(session_id):
    start_session_dt = datetime.now()
    
    print('Started \'process_files\' for {}'.format(session_id))
    
    db_conn = get_db()
    config = get_flask_config()
    
    session_info = get_session_status(db_conn, session_id)
    if session_info is None:
        print('Failed to find session with id {}'.format(session_id))
        close_connection(db_conn)
        return 

#     new_stage = SESSION_STAGE_TO_INDEX['relevance_classification_in_progress']
#     set_session_stage_to(db_conn, session_id, new_stage)
#     print('\'classify_for_relevance\' is in stage {}'.format(new_stage))

    process_files_internal(db_conn, session_id, config)

    new_stage = SESSION_STAGE_TO_INDEX['ready_for_review']
    set_session_stage_to(db_conn, session_id, new_stage)
    print('\'process_files\' is in stage {}'.format(new_stage))
    
    close_connection(db_conn)

    end_session_dt = datetime.now()
    print('process_files for session#{} took:'.format(session_id), end_session_dt - start_session_dt)
    return True

def move_files_to_procesing_dir(db_conn, session_id, config):

    local_incoming_session_dir, relative_session_dir = get_incoming_dir_for_session(session_id, config)
    local_processing_dir = config['PROCESSING_DIR']
    local_processing_session_dir = os.path.join(local_processing_dir, relative_session_dir)

    os.mkdir(local_processing_session_dir)

    processed_file_dict = []

    for row in query_db(db_conn, 'SELECT id, initial_path FROM files where session_id = ?', [session_id]):
        file_id = row['id']
        file_name = row['initial_path']

        local_incoming_file_path = os.path.join(local_incoming_session_dir, file_name)
        local_processing_file_path = os.path.join(local_processing_session_dir, file_name)

        if os.path.exists(local_incoming_file_path):
            shutil.move(local_incoming_file_path, local_processing_session_dir)

            upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, processing_path = ? WHERE id = ?'
                , [FILE_STAGE_TO_INDEX['moved_to_processing'], local_processing_file_path, file_id])

        else:
            err_msg = 'Problem locating file \'{}\''.format(local_incoming_file_path)
            print(err_msg)
            upsert_db(db_conn
                , 'UPDATE files SET file_stage = ?, error_message = ? WHERE id = ?'
                , [FILE_STAGE_TO_INDEX['errored'], err_msg, file_id])
 
    return True

def process_files_internal(db_conn, session_id, config):
    local_incoming_session_dir, relative_session_dir = get_incoming_dir_for_session(session_id, config)
    local_processing_dir = config['PROCESSING_DIR']
    local_processing_session_dir = os.path.join(local_processing_dir, relative_session_dir)
    
    options = {}
    options['SHOW_DEBUG_MESSAGES'] = False

    relevance_model = get_relevance_inference_model(config['RELEVANCE_MODEL_FILE'], options)
    if relevance_model is None:
        print('Error loading relevance model')
        return
    
    segmentation_model = get_segmentation_inference_model(config['SEGMENTATION_MODEL_FILE'], options)
    if segmentation_model is None:
        print('Error loading segmentation model')
        return
    
    classification_model = get_classification_inference_model(config['CLASSIFICATION_MODEL_FILE'], options)
    if classification_model is None:
        print('Error loading classification model')
        return 
    
    options['CLASSIFICATION_SIZE'] = config['CLASSIFICATION_RELEVANCE_SIZE']
    options['CLASSIFICATION_MASK_SIZE'] = config['CLASSIFICATION_MASK_SIZE']
    options['CLASSIFICATION_VIDEO_SIZE'] = config['CLASSIFICATION_VIDEO_SIZE']
    options['CLASSIFICATION_FRAMES_COUNT'] = config['CLASSIFICATION_FRAMES_COUNT']
    options['CLASSIFICATION_STEP'] = config['CLASSIFICATION_STEP']
    options['FRAME_SIZE'] = config['FRAME_SIZE']
    
    options['RELEVANCE_MODEL'] = relevance_model
    options['SEGMENTATION_MODEL'] = segmentation_model
    options['CLASSIFICATION_MODEL'] = classification_model

    options['CONVERT_TO_GRAY'] = config['CONVERT_TO_GRAY']
    options['PERSIST_FRAMES'] = config['PERSIST_FRAMES']
    
    options['PERSIST_FRAMES_DIRPATH'] =  os.path.join(local_processing_session_dir, config['PROCESSING_FRAME_DIR'])
    options['PERSIST_MAXFRAME_DIRPATH'] =  os.path.join(local_processing_session_dir, config['PROCESSING_MAXFRAME_DIR']) 
    options['MASKS_TARGET_PATH'] = os.path.join(local_processing_session_dir, config['PROCESSING_MASK_DIR'])
    options['PERSIST_SEGMENTED_FRAMES_DIRPATH'] = os.path.join(local_processing_session_dir, config['PROCESSING_SEGMENTED_DIR'])


    if options['PERSIST_FRAMES']:
        os.mkdir(options['PERSIST_FRAMES_DIRPATH'])
        
    os.mkdir(options['PERSIST_MAXFRAME_DIRPATH'])
    os.mkdir(options['MASKS_TARGET_PATH'])
    
    options['SHOW_GLOBAL_DEBUG_MESSAGES'] = True
    options['SHOW_DEBUG_MESSAGES'] = False

    for row in query_db(db_conn, 'SELECT id, processing_path, session_id, file_stage FROM files where session_id = ? and file_stage = ?', [session_id, FILE_STAGE_TO_INDEX['moved_to_processing']]):
        if options['SHOW_GLOBAL_DEBUG_MESSAGES']:
            _start = datetime.now()
            
        element = dbrecord_to_object_internal(row, options)        
        
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 1 failure', element)
            continue

        element = create_frame_for_classification_internal(element, options)
        if (element['break_processing']):
            #record reason
            if not element['is_supportedSOP']:
                element = save_file_stage_internal(element, options,db_conn, FILE_STAGE_TO_INDEX['ready_for_results'])
            else:
                if options['SHOW_DEBUG_MESSAGES']:
                    print('Step 2 failure', element)
            continue

        element = save_file_stage_internal(element, options,db_conn, FILE_STAGE_TO_INDEX['has_relevance_frame'])
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 3 failure', element)
            continue  
        
        element = get_relevance_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 4 failure', element)
            continue
        
        element = save_relevance_status_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 5 failure', element)
            continue
        
        # skip process of not relevant file
        if not element['relevant']:
            continue
        
        element = get_max_of_frames_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 6 failure', element)
            continue

        element = save_max_frame_path_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 7 failure', element)
            continue
        
        element = get_mask_for_dicom_internal(element, options)
        if (element['break_processing']):
            if options['SHOW_DEBUG_MESSAGES']:
                    print('Step 8 failure', element)
            continue

        element = save_file_stage_internal(element, options,db_conn, FILE_STAGE_TO_INDEX['has_mask_frame'])
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 9 failure', element)
            continue
        
        element = save_mask_resized_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 10 failure', element)
            continue
        
        element = save_mask_path_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 11 failure', element)
            continue
            
        element = save_mask_path_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 12 failure', element)
            continue
        
        element = prepare_pixel_data(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 13 failure', element)
            continue
        
        element = get_video_classification_internal(element, options)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 14 failure', element)
            continue
            
        element = save_video_classification_status_internal(element, options, db_conn)
        if (element['break_processing']):
            #record reason
            if options['SHOW_DEBUG_MESSAGES']:
                print('Step 15 failure', element)
            continue

        if options['SHOW_GLOBAL_DEBUG_MESSAGES']:
            _end = datetime.now()
            print('Completed processing of file {}. Time taken: {}'.format(row['id'], _end - _start))
    return True