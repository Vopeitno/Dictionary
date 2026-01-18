import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set

import requests

# Public LanguageTool API endpoint. [web:582]
LT_ENDPOINT = "https://api.languagetool.org/v2/check"


# --- Irregular verbs (base -> (V2, V3)) ---
IRREGULAR: Dict[str, Tuple[str, str]] = {
    "be": ("was/were", "been"),
    "become": ("became", "become"),
    "begin": ("began", "begun"),
    "break": ("broke", "broken"),
    "bring": ("brought", "brought"),
    "build": ("built", "built"),
    "buy": ("bought", "bought"),
    "catch": ("caught", "caught"),
    "choose": ("chose", "chosen"),
    "come": ("came", "come"),
    "do": ("did", "done"),
    "drink": ("drank", "drunk"),
    "drive": ("drove", "driven"),
    "eat": ("ate", "eaten"),
    "fall": ("fell", "fallen"),
    "feel": ("felt", "felt"),
    "find": ("found", "found"),
    "fly": ("flew", "flown"),
    "forget": ("forgot", "forgotten"),
    "get": ("got", "got/gotten"),
    "give": ("gave", "given"),
    "go": ("went", "gone"),
    "have": ("had", "had"),
    "hear": ("heard", "heard"),
    "know": ("knew", "known"),
    "leave": ("left", "left"),
    "lose": ("lost", "lost"),
    "make": ("made", "made"),
    "meet": ("met", "met"),
    "pay": ("paid", "paid"),
    "read": ("read", "read"),
    "run": ("ran", "run"),
    "say": ("said", "said"),
    "see": ("saw", "seen"),
    "sell": ("sold", "sold"),
    "send": ("sent", "sent"),
    "sit": ("sat", "sat"),
    "sleep": ("slept", "slept"),
    "speak": ("spoke", "spoken"),
    "spend": ("spent", "spent"),
    "stand": ("stood", "stood"),
    "take": ("took", "taken"),
    "teach": ("taught", "taught"),
    "tell": ("told", "told"),
    "think": ("thought", "thought"),
    "understand": ("understood", "understood"),
    "wear": ("wore", "worn"),
    "write": ("wrote", "written"),
}


OPTIONAL_TOKENS = {
    "a", "an", "the",
    "to", "in", "on", "at", "of", "for", "with", "about", "from", "into",
    "it", "this", "that", "these", "those",
    "my", "your", "his", "her", "our", "their",
    "me", "him", "her", "us", "them",
}


TENSES = [
    "Present Simple",
    "Past Simple",
    "Future Simple",
    "Present Continuous",
    "Past Continuous",
    "Future Continuous",
    "Present Perfect",
    "Past Perfect",
    "Future Perfect",
    "Present Perfect Continuous",
    "Past Perfect Continuous",
    "Future Perfect Continuous",
]


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _simple_forms(base: str) -> Set[str]:
    """
    Generate a minimal set of common forms for simple word usage detection:
    base, 3rd person, past, -ing, and irregular V2/V3 where known.
    """
    b = _norm(base)
    if not b:
        return set()

    forms = {b}

    # 3rd person / plural
    if b.endswith("y") and len(b) > 2 and b[-2] not in "aeiou":
        forms.add(b[:-1] + "ies")
    if b.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(b + "es")
    forms.add(b + "s")

    # past
    if b.endswith("e"):
        forms.add(b + "d")
    else:
        forms.add(b + "ed")

    # -ing
    if b.endswith("e") and not b.endswith("ee"):
        forms.add(b[:-1] + "ing")
    else:
        forms.add(b + "ing")

    # irregular
    if b in IRREGULAR:
        v2, v3 = IRREGULAR[b]
        for f in v2.split("/"):
            forms.add(_norm(f))
        for f in v3.split("/"):
            forms.add(_norm(f))

    return {f for f in forms if f}


def _required_content_tokens(required_word: str) -> List[str]:
    req = _tokens(required_word)
    return [t for t in req if t not in OPTIONAL_TOKENS]


def used_word_in_sentence(sentence: str, required_word: str) -> bool:
    """
    Checks that the required word (or its simple forms) appears in the sentence.
    For multi-token phrases: requires content tokens contiguously, and allows
    inflection only on the first token.
    """
    toks = _tokens(sentence)
    tokset = set(toks)

    content = _required_content_tokens(required_word)
    if not content:
        content = _tokens(required_word)

    if len(content) == 1:
        for f in _simple_forms(content[0]):
            if f in tokset:
                return True
        return False

    head = content[0]
    tail = content[1:]
    head_forms = _simple_forms(head)

    n = len(toks)
    m = len(tail)
    for i in range(n):
        if toks[i] not in head_forms:
            continue
        if i + m >= n:
            continue
        ok = True
        for j in range(m):
            if toks[i + 1 + j] != tail[j]:
                ok = False
                break
        if ok:
            return True
    return False


def _ends_with_ed(tok: str) -> bool:
    return tok.endswith("ed") and len(tok) > 3


def _looks_like_v3(tok: str) -> bool:
    if _ends_with_ed(tok):
        return True
    for _base, (_v2, v3) in IRREGULAR.items():
        if tok in [x.strip() for x in v3.split("/")]:
            return True
    return False


def _looks_like_v2(tok: str) -> bool:
    if _ends_with_ed(tok):
        return True
    for _base, (v2, _v3) in IRREGULAR.items():
        if tok in [x.strip() for x in v2.split("/")]:
            return True
    return False


def lt_online(timeout: float = 2.0) -> bool:
    """Быстрая проверка подключения с таймаутом"""
    try:
        r = requests.post(
            LT_ENDPOINT, 
            data={"text": "Hello.", "language": "en-US"}, 
            timeout=timeout
        )
        return r.status_code == 200
    except requests.exceptions.Timeout:
        return False
    except Exception:
        return False


def check_grammar_language_tool(sentence: str, lang: str = "en-US") -> List[dict]:
    """
    LanguageTool check с оптимизированным таймаутом
    """
    try:
        resp = requests.post(
            LT_ENDPOINT,
            data={
                "text": sentence, 
                "language": lang,
                "enabledOnly": "false"
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("matches", [])
    except requests.exceptions.Timeout:
        return [{"message": "Grammar check timeout", "rule": {"id": "timeout"}}]
    except Exception as e:
        return [{"message": f"Error: {str(e)}", "rule": {"id": "error"}}]


# --- Tense matcher with gaps (allows inserts like adverbs) ---

def _match_sequence_with_gaps(tokens: List[str], parts: List[Set[str]], max_gap: int) -> bool:
    """
    Find parts[0], then parts[1] ... in order, allowing up to max_gap tokens between parts.
    """
    n = len(tokens)
    starts = [i for i, t in enumerate(tokens) if t in parts[0]]
    for s in starts:
        pos = s
        ok = True
        for k in range(1, len(parts)):
            found = False
            for j in range(pos + 1, min(n, pos + 1 + max_gap + 1)):
                if tokens[j] in parts[k]:
                    pos = j
                    found = True
                    break
            if not found:
                ok = False
                break
        if ok:
            return True
    return False


def tense_heuristic_ok(sentence: str, tense: str) -> Tuple[bool, str]:
    toks = _tokens(sentence.strip())

    # allow 1-3 filler tokens between auxiliaries (e.g. "will just be working")
    G = 3

    if tense == "Future Simple":
        return (True, "Found 'will'.") if "will" in toks else (False, "Expected: will + V1.")

    if tense == "Past Simple":
        if "did" in toks:
            return True, "Found 'did'."
        if any(_looks_like_v2(t) for t in toks):
            return True, "Found V2 marker (-ed or irregular V2)."
        return False, "Expected: did + V1 or V2."

    if tense == "Present Simple":
        if "will" in toks or "had" in toks or "been" in toks:
            return False, "Looks like Future/Perfect (will/had/been found)."
        # If it looks like Continuous, reject
        ing = {t for t in toks if t.endswith("ing")}
        if ing and _match_sequence_with_gaps(toks, [set(["am", "is", "are"]), ing], 1):
            return False, "Looks like Continuous (be ... V-ing)."
        return True, "No strong markers of other tenses."

    if tense == "Present Continuous":
        ing = {t for t in toks if t.endswith("ing")}
        return (True, "Found am/is/are ... V-ing.") if (ing and _match_sequence_with_gaps(toks, [set(["am", "is", "are"]), ing], G)) else (False, "Expected: am/is/are ... V-ing.")

    if tense == "Past Continuous":
        ing = {t for t in toks if t.endswith("ing")}
        return (True, "Found was/were ... V-ing.") if (ing and _match_sequence_with_gaps(toks, [set(["was", "were"]), ing], G)) else (False, "Expected: was/were ... V-ing.")

    if tense == "Future Continuous":
        ing = {t for t in toks if t.endswith("ing")}
        return (True, "Found will ... be ... V-ing.") if (ing and _match_sequence_with_gaps(toks, [set(["will"]), set(["be"]), ing], G)) else (False, "Expected: will ... be ... V-ing.")

    if tense == "Present Perfect":
        v3 = {t for t in toks if _looks_like_v3(t)}
        return (True, "Found have/has ... V3.") if (v3 and _match_sequence_with_gaps(toks, [set(["have", "has"]), v3], G)) else (False, "Expected: have/has ... V3.")

    if tense == "Past Perfect":
        v3 = {t for t in toks if _looks_like_v3(t)}
        return (True, "Found had ... V3.") if (v3 and _match_sequence_with_gaps(toks, [set(["had"]), v3], G)) else (False, "Expected: had ... V3.")

    if tense == "Future Perfect":
        v3 = {t for t in toks if _looks_like_v3(t)}
        return (True, "Found will ... have ... V3.") if (v3 and _match_sequence_with_gaps(toks, [set(["will"]), set(["have"]), v3], G)) else (False, "Expected: will ... have ... V3.")

    if tense == "Present Perfect Continuous":
        ing = {t for t in toks if t.endswith("ing")}
        return (True, "Found have/has ... been ... V-ing.") if (ing and _match_sequence_with_gaps(toks, [set(["have", "has"]), set(["been"]), ing], G)) else (False, "Expected: have/has ... been ... V-ing.")

    if tense == "Past Perfect Continuous":
        ing = {t for t in toks if t.endswith("ing")}
        return (True, "Found had ... been ... V-ing.") if (ing and _match_sequence_with_gaps(toks, [set(["had"]), set(["been"]), ing], G)) else (False, "Expected: had ... been ... V-ing.")

    if tense == "Future Perfect Continuous":
        ing = {t for t in toks if t.endswith("ing")}
        return (True, "Found will ... have ... been ... V-ing.") if (ing and _match_sequence_with_gaps(toks, [set(["will"]), set(["have"]), set(["been"]), ing], G)) else (False, "Expected: will ... have ... been ... V-ing.")

    return False, "Unknown tense."


@dataclass
class SentenceCheckResult:
    ok: bool
    used_word: bool
    tense_ok: bool
    grammar_ok: bool
    message: str
    matches: List[dict]


def check_sentence(sentence: str, required_word: str, tense: str) -> SentenceCheckResult:
    used = used_word_in_sentence(sentence, required_word)
    tense_ok, tense_msg = tense_heuristic_ok(sentence, tense)

    matches: List[dict] = []
    grammar_ok = False
    grammar_msg = ""

    try:
        matches = check_grammar_language_tool(sentence, "en-US")
        grammar_ok = len(matches) == 0
        if grammar_ok:
            grammar_msg = "Grammar: OK."
        else:
            first = matches[0]
            grammar_msg = f"Grammar: {first.get('message', 'Errors found.')}"
    except Exception as e:
        grammar_ok = False
        grammar_msg = f"Grammar check error: {e}"

    ok = used and tense_ok and grammar_ok

    msg_parts = []
    if not used:
        msg_parts.append("Word not used (content token not found).")
    if not tense_ok:
        msg_parts.append(f"Tense mismatch: {tense_msg}")
    if not grammar_ok:
        msg_parts.append(grammar_msg)
    if ok:
        msg_parts.append("Correct.")

    return SentenceCheckResult(
        ok=ok,
        used_word=used,
        tense_ok=tense_ok,
        grammar_ok=grammar_ok,
        message=" ".join(msg_parts) if msg_parts else "OK",
        matches=matches,
    )