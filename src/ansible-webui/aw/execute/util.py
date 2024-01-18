from os import chmod
from pathlib import Path
from shutil import rmtree
from random import choice as random_choice
from string import digits
from datetime import datetime

from ansible_runner import Runner as AnsibleRunner

from aw.config.main import config
from aw.config.hardcoded import RUNNER_TMP_DIR_TIME_FORMAT
from aw.config.environment import check_aw_env_var_true, get_aw_env_var, check_aw_env_var_is_set
from aw.utils.util import get_choice_key_by_value
from aw.utils.handlers import AnsibleConfigError
from aw.model.job import Job, JobExecution, JobExecutionResult, JobExecutionResultHost, CHOICES_JOB_EXEC_STATUS


def _decode_env_vars(env_vars_csv: str, src: str) -> dict:
    try:
        env_vars = {}
        for kv in env_vars_csv.split(','):
            k, v = kv.split('=')
            env_vars[k] = v

        return env_vars

    except ValueError:
        raise AnsibleConfigError(
            f"Environmental variables of {src} are not in a valid format "
            f"(comma-separated key-value pairs). Example: 'key1=val1,key2=val2'"
        )


def _update_execution_status(execution: JobExecution, status: str):
    execution.status = get_choice_key_by_value(choices=CHOICES_JOB_EXEC_STATUS, value=status)
    execution.save()


def _runner_options(job: Job, execution: JobExecution) -> dict:
    # NOTES:
    #  playbook str or list
    #  project_dir = playbook_dir
    #  quiet
    #  limit, verbosity, envvars

    # build unique temporary execution directory
    path_run = config['path_run']
    if not path_run.endswith('/'):
        path_run += '/'

    path_run += datetime.now().strftime(RUNNER_TMP_DIR_TIME_FORMAT)
    path_run += ''.join(random_choice(digits) for _ in range(5))

    # merge job + execution env-vars
    env_vars = {}
    if job.environment_vars is not None:
        env_vars = {
            **env_vars,
            **_decode_env_vars(env_vars_csv=job.environment_vars, src='Job')
        }

    if execution.environment_vars is not None:
        env_vars = {
            **env_vars,
            **_decode_env_vars(env_vars_csv=execution.environment_vars, src='Execution')
        }

    opts = {
        'runner_mode': 'pexpect',
        'private_data_dir': path_run,
        'project_dir': config['path_play'],
        'quiet': True,
        'limit': execution.limit if execution.limit is not None else job.limit,
        'envvars': env_vars,
    }

    if check_aw_env_var_is_set('run_timeout'):
        opts['timeout'] = get_aw_env_var('run_timeout')

    if check_aw_env_var_true('run_isolate_dir'):
        opts['directory_isolation_base_path'] = path_run / 'play_base'

    if check_aw_env_var_true('run_isolate_process'):
        opts['process_isolation'] = True
        opts['process_isolation_hide_paths'] = get_aw_env_var('run_isolate_process_path_hide')
        opts['process_isolation_show_paths'] = get_aw_env_var('run_isolate_process_path_show')
        opts['process_isolation_ro_paths'] = get_aw_env_var('run_isolate_process_path_ro')

    return opts


def runner_prep(job: Job, execution: (JobExecution, None)) -> dict:
    if execution is None:
        execution = JobExecution(user=None, job=job, comment='Scheduled')

    _update_execution_status(execution, status='Starting')

    opts = _runner_options(job=job, execution=execution)
    opts['playbook'] = job.playbook.split(',')
    opts['inventory'] = job.inventory.split(',')

    # https://docs.ansible.com/ansible/2.8/user_guide/playbooks_best_practices.html#directory-layout
    project_dir = opts['project_dir']
    if not project_dir.endswith('/'):
        project_dir += '/'

    for playbook in opts['playbook']:
        ppf = project_dir + playbook
        if not Path(ppf).is_file():
            raise AnsibleConfigError(f"Configured playbook not found: '{ppf}'")

    for inventory in opts['inventory']:
        pi = project_dir + inventory
        if not Path(pi).exists():
            raise AnsibleConfigError(f"Configured inventory not found: '{pi}'")

    pdd = Path(opts['private_data_dir'])
    if not pdd.is_dir():
        pdd.mkdir()
        chmod(path=pdd, mode=0o750)

    _update_execution_status(execution, status='Running')

    return opts


def runner_cleanup(opts: dict):
    rmtree(opts['private_data_dir'])


def parse_run_result(execution: JobExecution, time_start: datetime, result: AnsibleRunner):
    job_result = JobExecutionResult(
        time_start=time_start,
        failed=result.errored,
    )
    job_result.save()

    # https://stackoverflow.com/questions/70348314/get-python-ansible-runner-module-stdout-key-value
    for host in result.stats['processed']:
        result_host = JobExecutionResultHost()

        result_host.unreachable = host in result.stats['unreachable']
        result_host.tasks_skipped = result.stats['skipped'][host] if host in result.stats['skipped'] else 0
        result_host.tasks_ok = result.stats['ok'][host] if host in result.stats['ok'] else 0
        result_host.tasks_failed = result.stats['failures'][host] if host in result.stats['failures'] else 0
        result_host.tasks_ignored = result.stats['ignored'][host] if host in result.stats['ignored'] else 0
        result_host.tasks_rescued = result.stats['rescued'][host] if host in result.stats['rescued'] else 0
        result_host.tasks_changed = result.stats['changed'][host] if host in result.stats['changed'] else 0

        if result_host.tasks_failed > 0:
            # todo: create errors
            pass

        result_host.result = job_result
        result_host.save()

    execution.result = job_result
    if job_result.failed:
        _update_execution_status(execution, status='Failed')

    else:
        _update_execution_status(execution, status='Finished')