"""Phase 0 smoke test 2: Prism choice / noul / score, same question in English, Hindi, Hinglish."""

from __future__ import annotations

import logging
import time

from brain.models import PrismDecider

logging.basicConfig(level=logging.WARNING)

OPTIONS = {
    "list_dir": "Look at what files are inside a folder",
    "read_file": "Read the text of one file",
    "search_files": "Find files by name or pattern",
    "system_info": "Show CPU, RAM or disk information",
}
STATES = {
    "english": "What is taking up space in my Downloads folder?",
    "hindi": "मेरे Downloads फ़ोल्डर में कितनी जगह कौन सी चीज़ घेर रही है?",
    "hinglish": "Mere Downloads folder mein kya sabse zyada space le raha hai?",
}
QUESTIONS = {
    "tool": {
        "type": "choice",
        "criteria": OPTIONS,
        "instructions": "Which tool should the assistant call first?",
    },
    "risky": {
        "type": "noul",
        "instructions": "Could carrying out this request lose data or contact someone?",
    },
    "urgency": {
        "type": "score",
        "criteria": ["not urgent", "somewhat", "moderate", "urgent", "critical"],
    },
}


def main() -> None:
    p = PrismDecider()
    rows = []
    for lang, state in STATES.items():
        t0 = time.perf_counter()
        r = p.ask(state, QUESTIONS)  # all three questions in ONE request
        dt = time.perf_counter() - t0
        a = r.answers
        rows.append(
            (
                lang,
                dt,
                r.usage.input_tokens,
                a["tool"].choice,
                a["tool"].confidence,
                a["tool"].probabilities[a["tool"].choice],
                a["risky"].noul,
                a["urgency"].score,
            )
        )
        print(f"{lang:9s} raw answers: {a}")
    print("\nlang       latency  in_tok  top_tool    conf   p_top  P(risky)  urgency")
    for lang, dt, tk, tool, conf, ptop, risky, urg in rows:
        print(
            f"{lang:9s}  {dt:5.2f}s  {tk:6d}  {tool:10s}  {conf:.3f}  {ptop:.3f}  {risky:.3f}     {urg:.2f}"
        )
    print("PASS")


if __name__ == "__main__":
    main()
