"""
20-总结：将所有的组件都组合进同一个loop中
"""

import ast,json,os,subprocess,time,random,threading,re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass,asdict,field
import yaml


try:
    import readline
    readline.parse_and_bind('set bind-tty-special-chars off')
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False


from anthropic import Anthropic
from dotenv import load_dotenv


#加载环境变量
load_dotenv(override=True)
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN",None)


#设置应答模型，加载环境变量中设定的模型
WORKDIR = Path.cwd()
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]
PRIMARY_MODEL = MODEL
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL_ID")


#设置skills等保存路径
SKILLS_DIR = WORKDIR / "skills"
TRANSCRIRT_DIR = WORKDIR / ".transcripts"
TOOL_RESULET_DIR = WORKDIR / ".task_outputs" / "tool-results"


#限制设定，如设置模型调用上限等
DEFAULT_MAX_TOKENS = 8000
ESCALATED_MAX_TOKENS = 16000
MAX_RETRIES = 3
MAX_CONSECUTIVE = 2
MAX_RECOVER_RETRIES = 2
BASE_DELAY_MS = 500
CONTEXT_LIMIT = 5000
KEEP_RECET_TOOL_RESULTS = 3
PESIST_THRESHOLD = 30000
CONTINUATION_PROMPT = "Continue from the previous response. Do not repeat completed work."
PROMPT = "\033[36ms20 >> \033[0m"
CLI_ACTIVE = False


#命令行打印输出
def terminal_print(text:str):
    if threading.current_thread() is threading.main_thread() or not CLI_ACTIVE:
        print(text)
        return
    line = ""
    if READLINE_AVAILABLE:
        try:
            line = readline.get_line_buffer()
        except Exception:
            line = ""
    print(f"\r\033[k{text}]")
    print(PROMPT + line, end="",flush=True)


#任务系统

#设置任务保存目录
TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)
CURRENT_TODOS: list[dict] = []


#定义后续需要的数据类型
@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str
    owenr: str | None
    blockedBy: list[str]
    worktree: str | None = None


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def create_task(subject: str, description: str = "",
                blockedBy: list[str] | None = None) -> Task:
    task = Task(
        id=f"task_{int(time.time())}_{random.randint(o,9999):04d}",
        subject=subject, description=description,
        status="pending",owenr=None,
        blockedBy=blockedBy or [],
    )
    save_task(task)
    return task


def save_task(task: Task):
    _task_path(task.id).write_text(json.dumps(asdict(task), indent=2))


def load_task(task:Task):
    _task_path(task.id).write_text(json.dumps(asdict(task),indent=2))


def list_tasks() -> list[Task]:
    return [Task(**json.loads(p.read_text()))
            for p in sorted(TASKS_DIR.glob("task_*.json"))]


def get_task_json(task_id: str) -> str:
    return json.dumps(asdict(load_task(task_id)),indent=2)


def can_start(task_id: str) -> bool:
    #确认状态，是否开始任务
    task = load_task(task_id)
    for dep_id in task.blockedBy:
        if not _task_path(dep_id).exists():
            return False
        if load_task(dep_id).status != "completed":
            return False
    return True


def claim_task(task_id: str, owner: str = "agent") -> str:
    task = load_task(task_id)
    if task.status != "pending":
        return f"Task {task_id} is {task.status},cannot claim"
    if task.owner:
        return f" Task {task_id} already owned by {task.owner}"
    if not can_start(task_id):
        deps = [d for f in task.blockedBy
                if _task_path(d).exists() and load_task(d).status != "completed"]
        missing = [d for d in task.blocedBy if not _task_path(d).exists()]
        parts = []
        if deps: parts.append(f"blocked by：{deps}")
        if missing: parts.append(f"missing deps: {missing}")
        return "Cannot start - "+",".join(parts)
    task.owner = owner
    task.status = "in_progress"
    save_task(task)
    print(f"\033[36m[claim] {task.subject} -> in_progress\033[0m")
    return f"Claim {task_id} ({task.subject})"


def complete_task(task_id: str) -> str:
    task = load_task(task_id)
    if task.status != "in_progress":
        return f"Task {task_id} is {task.status}, cannot complete"
    task.status = "completed"
    save_task(task)
    unblocked = [t.subject for t in list_tasks()
                 if t.status == "pending" and t.blockedBy and can_start(t.id)]
    print(f"  \033[32m[complete] {task.subject} ✓\033[0m")
    msg = f"Completed {task.id} ({task.subject})"
    if unblocked:
        msg += f"\nUnblocked: {', '.join(unblocked)}"
    return msg




#工作树系统