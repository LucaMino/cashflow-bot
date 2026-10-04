import json
import logging
import time
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

import litellm

from tools import Tool

log = logging.getLogger(__name__)

# litellm keeps Gemini's provider_specific_fields (thought signatures) as dicts in tool_calls: harmless
warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)

MAX_STEPS = 5


def system_prompt(tz: str) -> str:
    now = datetime.now(ZoneInfo(tz))
    return f"""\
        You are a personal expense tracker. The user sends short messages, usually in Italian, \
        describing expenses or income, or asking about past ones. You handle them with the tools provided.

        Today is {now:%A} {now.date().isoformat()} (timezone: {tz}).

        Rules:
        - Resolve relative dates ("ieri", "sabato scorso") against today. If no date is given, use today.
        - Italian number format: "1,20" means 1.20 and "1.200,50" means 1200.50. Tool arguments always use a dot as decimal separator.
        - Expenses are negative amounts, income is positive.
        - Payment method: use the one the user mentions (e.g. "con buddybank"); if none is mentioned, use "Contanti".
        - If the message is not about transactions, answer briefly without using tools.
        - If something essential is missing or ambiguous (e.g. no amount), ask one short question instead of guessing.

        After recording, reply with one line per transaction, formatted as "✅ <amount> <category>: <description>", \
        using the values returned by the tool. Reply in the user's language.
        Replies are shown as plain text in Telegram: never use Markdown or other formatting (no *, _, `, #); use simple lines and "-" for lists."""


def run(text: str, tools: dict[str, Tool], model: str, tz: str) -> str:
    msgs: list = [
        {"role": "system", "content": system_prompt(tz)},
        {"role": "user", "content": text},
    ]
    specs = [t.spec() for t in tools.values()]

    log.info("user: %r", text)
    for step in range(1, MAX_STEPS + 1):
        msg = litellm.completion(
            model=model, messages=msgs, tools=specs, num_retries=3
        ).choices[0].message

        if not msg.tool_calls:
            log.info("step %d: reply %r", step, msg.content)
            return msg.content or ""

        # append the tool call and its result to the messages, so the model can continue reasoning
        msgs.append(msg)
        log.info("step %d: %d tool call(s)", step, len(msg.tool_calls))
        for call in msg.tool_calls:
            # execute the tool call and append the result to the messages
            result = _execute(tools, call)
            content = json.dumps(result, default=str, ensure_ascii=False)
            log.info("  <- %s: %s", call.function.name, content)
            msgs.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": content,
            })

    log.warning("gave up after %d steps", MAX_STEPS)
    return "Sorry, I couldn't handle your request. Please try again with a simpler message."


def _execute(tools: dict[str, Tool], call) -> object:
    name, args = call.function.name, call.function.arguments
    start = time.monotonic()
    try:
        if name not in tools:
            return {"error": f"Unknown tool: {name}"}
        return tools[name].call(args)
    except Exception as e:  # validation, gspread, etc.: the model can self-correct
        log.warning("tool %s failed: %s", name, e)
        return {"error": str(e)}
    finally:
        log.info("  -> %s(%s) %.2fs", name, args, time.monotonic() - start)