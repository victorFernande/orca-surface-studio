from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import tomllib
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    root=Path(__file__).resolve().parents[1]
    expected=tomllib.loads((root/"pyproject.toml").read_text())["project"]["version"]
    version=os.environ["GITHUB_REF_NAME"].removeprefix("v")
    if version!=expected:
        raise SystemExit("A versão da release difere da versão do pacote.")
    oidc_url=os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]+"&"+urlencode({"audience":"orcacloud"})
    request=Request(oidc_url,headers={"Authorization":"Bearer "+os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urlopen(request,timeout=30) as response:
        token=json.load(response)["value"]
    event=json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    metadata={"version":version,"changelog":str(event.get("release",{}).get("body") or "")[:4000]}
    bundle=root/"dist"/"orca_wave_generator_any.py"
    boundary="orca-wave-"+secrets.token_hex(20)
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
          +json.dumps(metadata).encode()+b"\r\n"
          +f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{bundle.name}"\r\nContent-Type: text/x-python\r\n\r\n'.encode()
          +bundle.read_bytes()+f"\r\n--{boundary}--\r\n".encode())
    request=Request("https://api.orcaslicer.com/api/v1/plugin-publish/releases",data=body,
        headers={"Authorization":"Bearer "+token,"Content-Type":"multipart/form-data; boundary="+boundary},method="POST")
    with urlopen(request,timeout=60) as response:
        if response.status!=201:
            raise SystemExit("A publicação não foi confirmada.")
    print("Release publicada no OrcaCloud.")


if __name__=="__main__":
    main()
