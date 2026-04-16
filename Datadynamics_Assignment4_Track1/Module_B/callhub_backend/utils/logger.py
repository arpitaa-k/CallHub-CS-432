from utils.shard_manager import shard_manager
import os
from datetime import datetime


def _ensure_logs_dir():
    logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    logs_dir = os.path.abspath(logs_dir)
    if not os.path.isdir(logs_dir):
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception:
            pass
    return logs_dir


def _append_log(filename, line):
    try:
        logs_dir = _ensure_logs_dir()
        logfile = os.path.join(logs_dir, filename)
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass


def _touch_log(filename):
    try:
        logs_dir = _ensure_logs_dir()
        logfile = os.path.join(logs_dir, filename)
        with open(logfile, 'a', encoding='utf-8'):
            pass
    except Exception:
        pass


def log_login_event(username, status, member_id=None, reason=None, ip=None, user_agent=None, jti=None):
    """Append login/logout/security events to logs/login_audit.log."""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    line = (
        f"{timestamp}\tstatus={status}\tusername={username}\tmember_id={member_id}"
        f"\treason={reason or ''}\tip={ip or ''}\tjti={jti or ''}\tua={user_agent or ''}"
    )
    _append_log('login_audit.log', line)


def log_action(actor_id, table, record_id, action, source='API'):
    """Log action into Audit_Trail table and append a human-readable copy to logs/audit.log.

    The optional `source` field can be used to indicate whether the change originated from
    the application (`'API'`) or was produced by a DB trigger/other source (`'DB'`).
    """

    timestamp = datetime.utcnow().isoformat() + 'Z'
    line = f"{timestamp}\tactor={actor_id}\ttable={table}\trecord={record_id}\taction={action}\tsource={source}"

    # Keep only the audit copy for human-readable logs.
    _append_log('audit.log', line)

    try:
        shard_id = shard_manager.get_shard_id(actor_id)
        shard_manager.execute_on_shard(shard_id, """
            INSERT INTO shard_{}_audit_trail
            (actor_id, target_table, target_record_id, action_type, source)
            VALUES (%s,%s,%s,%s,%s)
        """.format(shard_id), (actor_id, table, record_id, action, source))
    except Exception:
        # fallback silently
        pass



# Ensure expected log files exist even before first event is written.
_touch_log('login_audit.log')
_touch_log('audit.log')