def pytest_addoption(parser):
    group = parser.getgroup("local-model-evaluation")
    group.addoption("--local-model", default=None, help="Explicit installed Ollama model tag")
    group.addoption("--token-counter", default=None, help="Reviewed local module:counter_factory")
    group.addoption("--eval-output", default="artifacts/local-model-evaluation/results.json")
