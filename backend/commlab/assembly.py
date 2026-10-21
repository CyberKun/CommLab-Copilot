import os
from pathlib import Path
from commlab.db import database, Base
from commlab.artifacts.api import Artifacts, LocalStore
from commlab.workspaces.api import Workspaces
from commlab.experiments.api import Experiments
from commlab.simulation.api import registry
from commlab.verification.api import Verifier, TheoryRule, SampleAdequacyRule
from commlab.knowledge.api import Knowledge, HashEmbedding, OllamaEmbedding
from commlab.retrieval.api import Retrieval, ReciprocalRankFusion
from commlab.investigations.api import Investigations, OfflinePlanner, OllamaProvider


class Services:
    def __init__(self, url=None, storage=None):
        Path("data").mkdir(exist_ok=True)
        self.engine, self.sessions = database(url)
        self.workspaces = Workspaces(self.sessions)
        self.artifacts = Artifacts(self.sessions, LocalStore(storage or os.getenv("ARTIFACT_ROOT", "data/artifacts")))
        self.capabilities = registry()
        self.verifier = Verifier([TheoryRule(), SampleAdequacyRule()])
        self.experiments = Experiments(self.sessions, self.capabilities, self.artifacts, self.verifier)
        ollama = os.getenv("OLLAMA_URL", "http://localhost:11434")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        self.embeddings = OllamaEmbedding(ollama, embedding_model, os.getenv("EMBEDDING_REVISION")) if embedding_model else HashEmbedding()
        self.knowledge = Knowledge(self.sessions, self.artifacts, self.embeddings)
        self.retrieval = Retrieval(self.knowledge, self.embeddings, ReciprocalRankFusion())
        model = os.getenv("LLM_MODEL")
        provider = OllamaProvider(ollama, model) if model else OfflinePlanner()
        self.investigations = Investigations(self.sessions, self.retrieval, self.experiments, self.artifacts, provider)

    def create_dev_schema(self):
        if self.engine.dialect.name != "sqlite":
            raise RuntimeError("Use Alembic for PostgreSQL.")
        from alembic import command
        from alembic.config import Config
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.attributes["use_environment_url"] = False
        config.set_main_option("script_location", str(root / "migrations"))
        config.set_main_option("sqlalchemy.url", str(self.engine.url).replace("%", "%%"))
        command.upgrade(config, "head")
