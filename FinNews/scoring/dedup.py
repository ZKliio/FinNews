import hashlib
import re
from datetime import timedelta

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "and", "but", "or", "nor",
    "not", "so", "very", "just", "than", "too", "also", "that", "this",
    "it", "its", "he", "she", "they", "we", "you", "i", "my", "your",
    "his", "her", "their", "our", "rt", "via",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9$]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def jaccard_similarity(a: str, b: str) -> float:
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def deduplicate(items: list, window_minutes: int = 5, threshold: float = 0.6) -> list:
    if not items:
        return items

    clusters: list[list] = []

    for item in sorted(items, key=lambda x: x.published_at):
        placed = False
        for cluster in clusters:
            representative = cluster[0]
            time_diff = abs((item.published_at - representative.published_at).total_seconds())
            if time_diff > window_minutes * 60:
                continue
            sim = jaccard_similarity(item.headline, representative.headline)
            if sim >= threshold:
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    for cluster in clusters:
        if len(cluster) == 1:
            continue

        cluster_id = hashlib.md5(cluster[0].headline[:50].encode()).hexdigest()[:12]

        best = max(cluster, key=lambda x: (
            len(x.body or ""),
            x.credibility,
            x.retweets + x.likes,
        ))

        for item in cluster:
            item.cluster_id = cluster_id
            item.is_primary = (item.id == best.id)

    return items
