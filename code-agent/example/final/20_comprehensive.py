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

