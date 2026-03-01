"""Simple RAG service for engineering context. Uses in-memory cosine similarity."""
from typing import Optional


class RAGService:
    """In-memory RAG using hash-based embeddings and cosine similarity."""

    def __init__(self):
        self.documents: list[dict] = []
        self.embeddings: list[list[float]] = []
        self._initialized = False

    def _init_default_docs(self):
        if self._initialized:
            return
        default_docs = [
            {"content": "Peng-Robinson EOS is best for hydrocarbon mixtures at moderate to high pressures. Use SRK as alternative.", "topic": "thermodynamics"},
            {"content": "NRTL is recommended for polar/non-ideal liquid mixtures like alcohol-water. UNIQUAC for polymer solutions.", "topic": "thermodynamics"},
            {"content": "Heat exchanger LMTD correction factor for shell-and-tube: use F-factor charts. NTU method preferred for rating problems.", "topic": "heat_transfer"},
            {"content": "Distillation: use FUG (Fenske-Underwood-Gilliland) for quick estimates. MESH for rigorous tray-by-tray.", "topic": "separation"},
            {"content": "Compressor polytropic efficiency typically 72-85%. Multi-stage with intercooling when compression ratio > 3.", "topic": "compression"},
            {"content": "NPSH available must exceed NPSH required by at least 1-2 meters to prevent cavitation.", "topic": "pumps"},
            {"content": "CSTR residence time distribution is exponential. PFR gives higher conversion for positive-order reactions.", "topic": "reactors"},
            {"content": "Ergun equation for packed bed pressure drop: combines Blake-Kozeny (laminar) and Burke-Plummer (turbulent).", "topic": "fluid_mechanics"},
            {"content": "Crystallization: cooling crystallization yields increase with larger temperature differential. Key compound MW determines crystal preference.", "topic": "separation"},
            {"content": "Three-phase separators split vapor/light-liquid/heavy-liquid using density differences. Size with Souders-Brown.", "topic": "separation"},
        ]
        for doc in default_docs:
            self.documents.append(doc)
            self.embeddings.append(self._simple_embed(doc["content"]))
        self._initialized = True

    @staticmethod
    def _simple_embed(text: str) -> list[float]:
        """Simple hash-based embedding (64-dim) — fallback when no ML model available."""
        words = text.lower().split()
        dim = 64
        vec = [0.0] * dim
        for w in words:
            idx = hash(w) % dim
            vec[idx] += 1.0
        norm = max(sum(v * v for v in vec) ** 0.5, 1e-10)
        return [v / norm for v in vec]

    def query(self, prompt: str, k: int = 3) -> list[str]:
        """Return top-k relevant documents by cosine similarity."""
        self._init_default_docs()
        if not self.documents:
            return []
        query_embed = self._simple_embed(prompt)
        scores = []
        for doc_embed in self.embeddings:
            dot = sum(a * b for a, b in zip(query_embed, doc_embed))
            scores.append(dot)
        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self.documents[i]["content"] for i in indices]


_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
