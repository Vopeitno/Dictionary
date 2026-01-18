import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set

import requests

LT_ENDPOINT = "https://api.languagetool.org/v2/check"


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


# Tokens that can be omitted from required "word/phrase" when checking "used in sentence".
# This is a pragmatic trainer heuristic, not strict linguistics. [web:472]
OPTIONAL_TOKENS = {
    "a",
    "an",
    "the",
    "to",
    "in",
    "on",
    "at",
    "of",
    "for",
    "with",
    "about",
    "from",
    "into",
    "it",
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "his",
    "her",
    "our",
    "their",
    "me",
    "him",
    "her",
    "us",
    "them",
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
    b = _norm(base)
    if not b:
        return set()

    forms = {b}

    # 3rd person
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
    """
    Convert required phrase to content tokens (remove optional tokens like 'the', 'it').
    Example:
      "sign it" -> ["sign"]
      "the effort" -> ["effort"]
      "believe in" -> ["believe"]
    """
    req = _tokens(required_word)
    return [t for t in req if t not in OPTIONAL_TOKENS]


def used_word_in_sentence(sentence: str, required_word: str) -> bool:
    toks = _tokens(sentence)
    tokset = set(toks)

    content = _required_content_tokens(required_word)

    # If after removing optional tokens nothing remains, fallback to raw tokens
    if not content:
        content = _tokens(required_word)

    # Single content token -> check inflected forms
    if len(content) == 1:
        for f in _simple_forms(content[0]):
            if f in tokset:
                return True
        return False

    # Phrase content tokens -> require them contiguously in order.
    # Allow inflection only on the first content token (usually the verb).
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
        forms = [x.strip() for x in v3.split("/")]
        if tok in forms:
            return True
    return False


def _looks_like_v2(tok: str) -> bool:
    if _ends_with_ed(tok):
        return True
    for _base, (v2, _v3) in IRREGULAR.items():
        forms = [x.strip() for x in v2.split("/")]
        if tok in forms:
            return True
    return False


def lt_online(timeout: float = 2.5) -> bool:
    try:
        r = requests.post(
            LT_ENDPOINT, data={"text": "Hello.", "language": "en-US"}, timeout=timeout
        )
        return r.status_code == 200
    except Exception:
        return False


def check_grammar_language_tool(sentence: str, lang: str = "en-US") -> List[dict]:
    resp = requests.post(
        LT_ENDPOINT,
        data={"text": sentence, "language": lang},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("matches", [])


def tense_heuristic_ok(sentence: str, tense: str) -> Tuple[bool, str]:
    toks = _tokens(sentence.strip())

    has_will = "will" in toks
    has_had = "had" in toks
    has_been = "been" in toks
    has_am_is_are = any(t in toks for t in ["am", "is", "are"])
    has_was_were = any(t in toks for t in ["was", "were"])

    def has_ing_after(aux_set: List[str]) -> bool:
        for i, t in enumerate(toks[:-1]):
            if t in aux_set and toks[i + 1].endswith("ing"):
                return True
        return False

    def has_have_v3() -> bool:
        for i, t in enumerate(toks[:-1]):
            if t in ["have", "has"] and _looks_like_v3(toks[i + 1]):
                return True
        return False

    def has_had_v3() -> bool:
        for i, t in enumerate(toks[:-1]):
            if t == "had" and _looks_like_v3(toks[i + 1]):
                return True
        return False

    def has_will_have_v3() -> bool:
        for i in range(len(toks) - 2):
            if (
                toks[i] == "will"
                and toks[i + 1] == "have"
                and _looks_like_v3(toks[i + 2])
            ):
                return True
        return False

    def has_will_be_ing() -> bool:
        for i in range(len(toks) - 2):
            if (
                toks[i] == "will"
                and toks[i + 1] == "be"
                and toks[i + 2].endswith("ing")
            ):
                return True
        return False

    def has_have_been_ing() -> bool:
        for i in range(len(toks) - 2):
            if (
                toks[i] in ["have", "has"]
                and toks[i + 1] == "been"
                and toks[i + 2].endswith("ing")
            ):
                return True
        return False

    def has_had_been_ing() -> bool:
        for i in range(len(toks) - 2):
            if (
                toks[i] == "had"
                and toks[i + 1] == "been"
                and toks[i + 2].endswith("ing")
            ):
                return True
        return False

    def has_will_have_been_ing() -> bool:
        for i in range(len(toks) - 3):
            if (
                toks[i] == "will"
                and toks[i + 1] == "have"
                and toks[i + 2] == "been"
                and toks[i + 3].endswith("ing")
            ):
                return True
        return False

    if tense == "Future Simple":
        return (True, "Found 'will'.") if has_will else (False, "Expected: will + V1.")

    if tense == "Past Simple":
        if "did" in toks:
            return True, "Found 'did'."
        if any(_looks_like_v2(t) for t in toks):
            return True, "Found V2 marker (-ed or irregular V2)."
        return False, "Expected: did + V1 or V2."

    if tense == "Present Simple":
        if has_will or has_had or has_been:
            return False, "Looks like Future/Perfect (will/had/been found)."
        if (has_am_is_are or has_was_were) and any(t.endswith("ing") for t in toks):
            return False, "Looks like Continuous (be + V-ing)."
        return True, "No strong markers of other tenses."

    if tense == "Present Continuous":
        return (
            (True, "Found am/is/are + V-ing.")
            if has_ing_after(["am", "is", "are"])
            else (False, "Expected: am/is/are + V-ing.")
        )

    if tense == "Past Continuous":
        return (
            (True, "Found was/were + V-ing.")
            if has_ing_after(["was", "were"])
            else (False, "Expected: was/were + V-ing.")
        )

    if tense == "Future Continuous":
        return (
            (True, "Found will be + V-ing.")
            if has_will_be_ing()
            else (False, "Expected: will be + V-ing.")
        )

    if tense == "Present Perfect":
        return (
            (True, "Found have/has + V3.")
            if has_have_v3()
            else (False, "Expected: have/has + V3.")
        )

    if tense == "Past Perfect":
        return (
            (True, "Found had + V3.")
            if has_had_v3()
            else (False, "Expected: had + V3.")
        )

    if tense == "Future Perfect":
        return (
            (True, "Found will have + V3.")
            if has_will_have_v3()
            else (False, "Expected: will have + V3.")
        )

    if tense == "Present Perfect Continuous":
        return (
            (True, "Found have/has been + V-ing.")
            if has_have_been_ing()
            else (False, "Expected: have/has been + V-ing.")
        )

    if tense == "Past Perfect Continuous":
        return (
            (True, "Found had been + V-ing.")
            if has_had_been_ing()
            else (False, "Expected: had been + V-ing.")
        )

    if tense == "Future Perfect Continuous":
        return (
            (True, "Found will have been + V-ing.")
            if has_will_have_been_ing()
            else (False, "Expected: will have been + V-ing.")
        )

    return False, "Unknown tense."


@dataclass
class SentenceCheckResult:
    ok: bool
    used_word: bool
    tense_ok: bool
    grammar_ok: bool
    message: str
    matches: List[dict]


def check_sentence(
    sentence: str, required_word: str, tense: str
) -> SentenceCheckResult:
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
