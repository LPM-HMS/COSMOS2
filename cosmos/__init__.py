from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
import sys
import os

from .db import Base


# turn SQLAlchemy warnings into errors
import warnings
from sqlalchemy.exc import SAWarning

warnings.simplefilter("error", SAWarning)

opj = os.path.join

# #######################################################################################################################
# Settings
# #######################################################################################################################

library_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(library_path, 'VERSION'), 'r') as fh:
    __version__ = fh.read().strip()


def default_get_submit_args(drm, task, default_queue=None):
    """
    Default method for determining the arguments to pass to the drm specified by :param:`drm`

    :returns: (str) arguments.  For example, returning "-n 3" if :param:`drm` == 'lsf' would caused all jobs
      to be submitted with bsub -n 3.  Returns None if no native_specification is required.
    """

    cpu_req = task.cpu_req
    mem_req = task.mem_req
    time_req = task.time_req
    jobname = '%s_task(%s)' % (task.stage.name, task.id)

    if 'lsf' in drm:
        return '-R "rusage[mem={mem}] span[hosts=1]" -n {cpu}{time}{queue} -J "{jobname}"'.format(mem=(mem_req or 0) / cpu_req,
                                                                                                  cpu=cpu_req,
                                                                                                  time=' -W 0:{0}'.format(time_req) if time_req else '',
                                                                                                  queue=' -q %s' % default_queue if default_queue else '',
                                                                                                  jobname=jobname)
    elif 'ge' in drm:
        # return '-l h_vmem={mem_req}M,num_proc={cpu_req}'.format(
        return '-pe smp {cpu_req}{queue} -N "{jobname}"'.format(mem_req=mem_req,
                                                                cpu_req=cpu_req,
                                                                queue=' -q %s' % default_queue if default_queue else '',
                                                                jobname=jobname)
    elif drm == 'local':
        return None
    else:
        raise Exception('DRM not supported')


class Cosmos(object):
    def __init__(self, database_url, get_submit_args=default_get_submit_args, default_drm='local', default_queue=None, flask_app=None):
        """

        :param database_url: a sqlalchemy database url.  ex: sqlite:///home/user/sqlite.db or mysql://user:pass@localhost/insilico
        :param get_submit_args: a function that returns arguments to be passed to the job submitter, like resource requirements or the queue to submit to.
            see :func:`default_get_submit_args` for details
        :param flask_app: a Flask application instance for the web interface.  The default behavior is to create one.
        """
        assert default_drm in ['local','lsf','ge'], 'unsupported drm: %s' % default_drm

        if '://' not in database_url:
            if database_url[0] != '/':
                # database_url is a relative root_path
                database_url = 'sqlite:///%s/%s' % (os.getcwd(), database_url)
            else:
                database_url = 'sqlite:///%s' % database_url

        self.flask_app = flask_app if flask_app else Flask(__name__)
        self.get_submit_args = get_submit_args
        self.flask_app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        self.sqla = SQLAlchemy(self.flask_app)
        self.session = self.sqla.session
        self.default_queue = default_queue
        self.default_drm = default_drm

    def initdb(self):
        """
        Initialize the database via sql CREATE statements
        """
        print >> sys.stderr, 'Initializing sql database for Cosmos v%s...' % __version__
        Base.metadata.create_all(bind=self.session.bind)
        from .db import MetaData

        meta = MetaData(initdb_library_version=__version__)
        self.session.add(meta)
        self.session.commit()

    def resetdb(self):
        """
        Resets the database.  This is not reversible!
        """
        print >> sys.stderr, 'Dropping tables in db...'
        Base.metadata.drop_all(bind=self.session.bind)
        self.initdb()

    def shell(self):
        """
        Launch an IPython shell with useful variables already imported
        """
        cosmos_app = self
        session = self.session
        executions = self.session.query(Execution).order_by('id').all()
        ex = executions[-1] if len(executions) else None

        import IPython

        IPython.embed()

    def runweb(self, host, port, debug=True):
        """
        Starts the web dashboard
        """
        return self.flask_app.run(debug=debug, host=host, port=port)


# #######################################################################################################################
# Misc
# #######################################################################################################################

class ExecutionFailed(Exception): pass

# #######################################################################################################################
# Signals
########################################################################################################################
import blinker

signal_task_status_change = blinker.Signal()
signal_stage_status_change = blinker.Signal()
signal_execution_status_change = blinker.Signal()


########################################################################################################################
# Enums
########################################################################################################################
import enum


class MyEnum(enum.Enum):
    def __str__(self):
        return "%s" % (self._value_)


class TaskStatus(MyEnum):
    no_attempt = 'Has not been attempted',
    waiting = 'Waiting to execute',
    submitted = 'Submitted to the job manager',
    successful = 'Finished successfully',
    failed = 'Finished, but failed'
    killed = 'Manually killed'


class StageStatus(MyEnum):
    no_attempt = 'Has not been attempted',
    running = 'Running',
    running_but_failed = 'Running, but a task failed'
    successful = 'Finished successfully',
    failed = 'Finished, but failed'
    killed = 'Manually killed'


class ExecutionStatus(MyEnum):
    no_attempt = 'Has not been attempted',
    running = 'Execution is running',
    successful = 'Finished successfully',
    killed = 'Manually killed'
    failed_but_running = "Running, but a task failed"
    failed = 'Finished, but failed'


class RelationshipType(MyEnum):
    one2one = 'one2one',
    one2many = 'one2many',
    many2one = 'many2one',
    many2many = 'many2many'


########################################################################################################################
# Imports
########################################################################################################################

from .graph import rel
from .models.TaskFile import TaskFile, abstract_output_taskfile, abstract_input_taskfile
from .models.Task import Task
from .models.Stage import Stage
from .models.Tool import Tool, Input, Inputs, chain
from .models.Execution import Execution
from .util.args import add_execution_args
from .graph.recipe import Recipe
# from .db import get_session


__all__ = ['rel', 'Recipe', 'TaskFile', 'Task', 'Inputs', 'rel', 'Stage', 'Execution', 'TaskStatus', 'StageStatus',
           'Tool', 'chain']