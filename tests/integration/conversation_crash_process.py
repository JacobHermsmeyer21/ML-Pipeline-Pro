"""Disposable real chat API; pause after the domain API accepted a submission."""

import argparse
import asyncio
import json
from pathlib import Path

import uvicorn

from ml_pipeline_pro import conversation_api
from ml_pipeline_pro.config import Settings
from ml_pipeline_pro.main import create_app
from ml_pipeline_pro.tool_transport import HttpToolTransport


def accepted(path, record_id):
    destination = Path(path)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps({"accepted_id": record_id}), encoding="utf-8")
    temporary.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--signal")
    args = parser.parse_args()

    class PauseAfterAcceptance(HttpToolTransport):
        async def request(self, method, path, **kwargs):
            result = await super().request(method, path, **kwargs)
            if args.signal and method == "POST" and result.status_code == 202:
                await asyncio.to_thread(accepted, args.signal, result.payload["id"])
                await asyncio.Event().wait()
            return result

    conversation_api.HttpToolTransport = PauseAfterAcceptance
    uvicorn.run(
        create_app(Settings(_env_file=None)), host="127.0.0.1", port=args.port, log_level="warning"
    )


if __name__ == "__main__":
    main()
