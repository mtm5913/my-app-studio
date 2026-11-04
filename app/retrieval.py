"""Small local lexical RAG index with traceable, versioned USDA passages."""

from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import re

CORPUS = Path(__file__).parent / "knowledge" / "usda-foods.json"
STOP = set(
    (
        "a an and are as at be can do does for from how i in is it me my of on or "
        "please some that the their them there these they this to us what which with "
        "would you your about tell give explain more example examples food foods"
    ).split()
)
ALIASES = {
    "veggies": "vegetable",
    "veggie": "vegetable",
    "vegetables": "vegetable",
    "grains": "grain",
    "beans": "bean",
    "alternatives": "alternate",
    "alternative": "alternate",
    "proteins": "protein",
    "lentils": "lentil",
    "peas": "pea",
    "nuts": "nut",
    "seeds": "seed",
}
REFUSAL = (
    "I can't answer that from Olive's USDA food collection. "
    "It doesn't contain enough relevant information for this question. "
    "Try asking about whole grains, vegetables, beans or meat alternatives."
)


def terms(text):
    """Normalize a few food plurals without introducing a heavyweight service."""
    return [
        ALIASES.get(word, word)
        for word in re.findall(r"[a-z]+", text.lower())
        if word not in STOP and len(word) > 2
    ]


@lru_cache(maxsize=1)
def collection():
    """Load only the reviewed repository corpus, never paths supplied by users."""
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def retrieve(question, history=()):
    """Rank passages by TF-IDF overlap; short follow-ups reuse prior user topics."""
    query = set(terms(question))
    followup = re.search(
        r"\b(it|they|them|those|these|that|more|another)\b", question.lower()
    )
    if followup and history:
        previous = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"), ""
        )
        query.update(terms(previous))
    if not query:
        return []
    passages = collection()["passages"]
    counts = [Counter(terms(p["text"] + " " + p["title"])) for p in passages]
    weights = {
        term: math.log(1 + len(passages) / (1 + sum(term in c for c in counts)))
        for term in query
    }
    ranked = []
    for passage, count in zip(passages, counts):
        overlap = query.intersection(count)
        score = sum(weights[t] * (1 + math.log(count[t])) for t in overlap)
        # A topic match is a retrieval heuristic, not proof that the answer exists.
        if overlap and score >= 0.9:
            ranked.append((score, passage))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [dict(p, citation=index + 1) for index, (_, p) in enumerate(ranked[:3])]


def sources(passages):
    """Citation URLs and IDs are server-selected, never invented by the model."""
    return [
        {
            "id": p["citation"],
            "title": p["title"],
            "url": p["url"],
            "section": p["section"],
            "excerpt": p["text"],
        }
        for p in passages
    ]
