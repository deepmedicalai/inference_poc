import os

from flask import Flask, g, send_from_directory, jsonify, session, request, current_app
from flask_cors import CORS, cross_origin
import logging
import sqlite3




def validate_edge_token(request):

    if request is None:
        return False, None

    token = request.headers.get("X-Api-Key")

    if (token is not None) and (token == "edge0001-key"):
        return True, token
    else:
        return False, None




def create_app(script_info=None):

    # instantiate the app
    app = Flask(
        __name__, static_url_path=''
    )

    # set config
    app_settings = os.getenv('APP_SETTINGS')
    app.config.from_object(app_settings)

    app.secret_key = app.config.get('SECRET_KEY')

    CORS(app)

    @app.route('/static/<path:filename>')
    def serve_static(filename):
        root_dir = os.path.dirname(os.getcwd())
        return send_from_directory(os.path.join(root_dir, 'main', app.config.get('STATIC_FOLDER')), filename)


    ## DB stuff
    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    def create_connection(db_file):
        """ create a database connection to the SQLite database
            specified by db_file
        :param db_file: database file
        :return: Connection object or None
        """
        try:
            conn = sqlite3.connect(db_file)
            return conn
        except Exception as e:
            print(e)
    
        return None

    def create_table(conn, create_table_sql):
        """ create a table from the create_table_sql statement
        :param conn: Connection object
        :param create_table_sql: a CREATE TABLE statement
        :return:
        """
        try:
            c = conn.cursor()
            c.execute(create_table_sql)
        except Exception as e:
            print(e)

    def init_database():
        sql_create_sessions_table = """ CREATE TABLE IF NOT EXISTS sessions (
                                            id integer PRIMARY KEY,
                                            stage integer NOT NULL,
                                            file_count integer NOT NULL,
                                            error_message text,
                                            begin_date text,
                                            end_date text
                                        ); """
    
        sql_create_files_table = """CREATE TABLE IF NOT EXISTS files (
                                        id integer PRIMARY KEY,
                                        session_id integer NOT NULL,
                                        file_name text NOT NULL,
                                        file_stage integer NOT NULL,
                                        initial_path text NOT NULL,
                                        processing_path text,
                                        relevance_result text,
                                        error_message text,
                                        begin_date text NOT NULL,
                                        end_date text NOT NULL,
                                        FOREIGN KEY (session_id) REFERENCES sessions (id)
                                    );"""
    
        # create a database connection
        conn = create_connection(current_app.config['DATABASE'])
        if conn is not None:
            # create projects table
            create_table(conn, sql_create_sessions_table)
            # create tasks table
            create_table(conn, sql_create_files_table)

        else:
            current_app.logger.error("Error! cannot create the database connection.")



    @app.before_first_request
    def activate_db():
        app.logger.info('Initializing db.')
        init_database()
        app.logger.info('Initialized db.')


    # register blueprints
    from webserver.main.api import api_blueprint
    from webserver.main.edge import edge_blueprint
    app.register_blueprint(api_blueprint)
    app.register_blueprint(edge_blueprint)

    # shell context for flask cli
    app.shell_context_processor({'app': app})

    return app

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(current_app.config['DATABASE'])
    return db

def query_db(db_conn, query, args=(), one=False):
    cur = db_conn.cursor()
    cur.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
            for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv

def upsert_db(db_conn, query, args=()):
    cur = db_conn.cursor()
    cur.execute(query, args)
    db_conn.commit()

def delete_db(db_conn, query, args=()):
    cur = db_conn.cursor()
    cur.execute(query, args)
    db_conn.commit()

 