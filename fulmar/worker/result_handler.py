# -*- encoding: utf-8 -*-
import time
import logging
from concurrent.futures import ThreadPoolExecutor

from .response import rebuild_response
from .project_manager import ProjectManager

logger = logging.getLogger(__name__)


class Processor(object):
    PROCESS_TIME_LIMIT = 30
    EXCEPTION_LIMIT = 3
    executor = ThreadPoolExecutor(max_workers=5)

    def __init__(self, newtask_queue, resultdb, projectdb, enable_stdout_capture=True):
        self.newtask_queue = newtask_queue
        self.resultdb = resultdb
        self.enable_stdout_capture = enable_stdout_capture
        self.project_manager = ProjectManager(projectdb, dict(
            enable_stdout_capture=self.enable_stdout_capture,
        ))
        self.executor = ThreadPoolExecutor(max_workers=5)

    def handle_result(self, task, result):
        '''Deal one response result'''
        start_time = time.time()
        response = rebuild_response(result)
        follows = []
        try:
            assert 'taskid' in task, 'need taskid in task'
            project_name = task['project_name']
            project_id = task['project_id']

            project_data = self.project_manager.get(project_name, project_id)
            assert project_data, "No such project!"

            if project_data.get('exception'):
                logger.error(project_data.get('exception_log'))
            else:
                logger.info('Sccceed in getting project data.')
                results, follows, db_name, coll_name = project_data['instance'].run_task(
                    project_data['module'],
                    task,
                    response
                )
                return (results, follows, db_name, coll_name)
        except Exception as e:
            logger.exception(e)

        process_time = time.time() - start_time
        logger.info('Process time cost: %s' % str(process_time))

        return (None, None, None, None)

    def put_tasks(self, tasks):
        self.executor.submit(self.newtask_queue.put, *tasks)

    def put_results(self, results, db_name, coll_name, task, query=None):
        self.executor.submit(self.save2db, results, db_name, coll_name, task, query=query)

    def save2db(self, results, db_name, coll_name, task, query=None):
        self.resultdb.update(db_name, coll_name, results, task, query=query)
